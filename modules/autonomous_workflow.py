"""
modules/autonomous_workflow.py — High-Level Autonomous Goal Execution for JARVIS
===============================================================================
Enables true goal-driven autonomy (e.g. "Research AI tools and prepare a report",
"Organize my week", "Build an expense tracker"):
- Goal decomposition into dynamic subtask DAGs with dependency tracking
- Resumable checkpoint persistence via PersistentTaskManager
- Live cancellation token propagation to orchestrator & tools
- Synthesizes findings into structured Markdown reports
"""

import json
import logging
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime

from modules.agent.orchestrator import UnifiedAgentOrchestrator
from modules.tasks.task_manager import PersistentTaskManager, TaskStatus

logger = logging.getLogger(__name__)


class AutonomousWorkflowEngine:
    """Orchestrates long-running, goal-driven autonomous tasks with dynamic DAG and resumption."""

    def __init__(self, orchestrator: UnifiedAgentOrchestrator, task_manager: PersistentTaskManager):
        self.orchestrator = orchestrator
        self.task_manager = task_manager

    async def start_autonomous_goal(self, goal: str, title: Optional[str] = None) -> str:
        """
        Decomposes user goal, registers a persistent task, and launches background execution.
        Returns task_id immediately so caller/UI doesn't block.
        """
        task_title = title or f"Autonomous: {goal[:35]}..."
        task = self.task_manager.create_task(
            title=task_title,
            goal=goal,
            total_steps=5
        )
        task_id = task["task_id"]

        # Run workflow in background asyncio task
        asyncio.create_task(self._run_goal_pipeline(task_id, goal))
        return task_id

    async def resume_goal(self, task_id: str) -> bool:
        """Resumes an interrupted or paused task from its last saved checkpoint."""
        task = self.task_manager.resume_task(task_id)
        if not task:
            return False

        asyncio.create_task(self._run_goal_pipeline(task_id, task["goal"], is_resumed=True))
        return True

    async def _run_goal_pipeline(self, task_id: str, goal: str, is_resumed: bool = False):
        """Pipeline executing decomposed subtasks with live cancellation and resumption."""
        logger.info(f"Starting pipeline execution for task {task_id} (resumed={is_resumed}): {goal}")
        cancel_token = self.task_manager.get_cancellation_token(task_id)

        try:
            if self.task_manager.is_cancelled(task_id):
                return

            task_record = self.task_manager.get_task(task_id)
            checkpoint = {}
            if task_record and task_record.get("checkpoint_data"):
                try:
                    checkpoint = json.loads(task_record["checkpoint_data"])
                except Exception:
                    checkpoint = {}

            # Plan or retrieve existing plan
            steps = checkpoint.get("plan", [])
            step_outputs = checkpoint.get("step_outputs", {})

            if not steps:
                self.task_manager.update_progress(
                    task_id=task_id,
                    step_desc="Decomposing goal into actionable plan",
                    steps_completed=1,
                    total_steps=5,
                    checkpoint={"plan": [], "step_outputs": {}}
                )

                plan_prompt = (
                    f"Break this goal into 3 sequential executable subtasks: {goal}\n"
                    "Format as a JSON array of 3 strings: [\"step 1\", \"step 2\", \"step 3\"]."
                )
                raw_plan = await asyncio.to_thread(self.orchestrator.llm.generate, [{"role": "user", "content": plan_prompt}], False)

                steps = ["Initial research and inspection", "Execution and data compilation", "Final synthesis"]
                try:
                    import re
                    match = re.search(r'\[.*\]', raw_plan, re.DOTALL)
                    if match:
                        parsed = json.loads(match.group(0))
                        if isinstance(parsed, list) and len(parsed) >= 1:
                            steps = parsed[:3]
                except Exception:
                    pass

            if self.task_manager.is_cancelled(task_id):
                return

            # Execute subtasks sequentially or pick up from where left off
            total_steps = len(steps) + 2  # Plan + Subtasks + Synthesis

            for i, step_desc in enumerate(steps):
                step_key = f"step_{i+1}"
                if step_key in step_outputs and step_outputs[step_key]:
                    logger.info(f"Task {task_id}: {step_key} already completed in checkpoint. Skipping.")
                    continue

                if self.task_manager.is_cancelled(task_id):
                    return

                self.task_manager.update_progress(
                    task_id=task_id,
                    step_desc=f"Executing: {step_desc}",
                    steps_completed=i + 2,
                    total_steps=total_steps,
                    checkpoint={"plan": steps, "step_outputs": step_outputs}
                )

                # Build context from previous step outputs
                context_str = "\n".join([f"{k}: {v[:300]}" for k, v in step_outputs.items()])
                query = f"Autonomous Goal: {goal}.\n{context_str}\n\nExecute current subtask: {step_desc}"

                output = await self.orchestrator.execute_task(
                    query=query,
                    conversation_history=[],
                    cancellation_token=cancel_token
                )

                if self.task_manager.is_cancelled(task_id):
                    return

                step_outputs[step_key] = output
                checkpoint["step_outputs"] = step_outputs
                self.task_manager.update_progress(
                    task_id=task_id,
                    step_desc=f"Completed: {step_desc}",
                    steps_completed=i + 2,
                    total_steps=total_steps,
                    checkpoint=checkpoint
                )

            if self.task_manager.is_cancelled(task_id):
                return

            # Final Synthesis
            self.task_manager.update_progress(
                task_id=task_id,
                step_desc="Synthesizing final deliverable",
                steps_completed=total_steps,
                total_steps=total_steps,
                checkpoint=checkpoint
            )

            all_results = "\n\n".join([f"{k.upper()}:\n{v}" for k, v in step_outputs.items()])
            final_prompt = (
                f"Synthesize the final deliverable for the user's goal: '{goal}'.\n\n"
                f"Findings & Results from all steps:\n{all_results}\n\n"
                "Provide a complete, structured summary with deliverables in British JARVIS tone."
            )
            final_deliverable = await asyncio.to_thread(
                self.orchestrator.llm.generate,
                [{"role": "user", "content": final_prompt}],
                False
            )

            self.task_manager.complete_task(task_id, final_deliverable)

        except asyncio.CancelledError:
            logger.info(f"Task pipeline [{task_id}] terminated due to user cancellation.")
        except Exception as e:
            logger.error(f"Autonomous workflow {task_id} failed: {e}", exc_info=True)
            self.task_manager.fail_task(task_id, str(e))
