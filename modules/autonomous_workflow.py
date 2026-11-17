"""
modules/autonomous_workflow.py — High-Level Autonomous Goal Execution for JARVIS
===============================================================================
Enables true goal-driven autonomy (e.g. "Research AI tools and prepare a report",
"Organize my week", "Build an expense tracker"):
- Goal decomposition into sequential subtask DAGs
- Checkpoint persistence via PersistentTaskManager
- Autonomous tool execution loop with error recovery
- Synthesizes findings into structured Markdown / PDF reports
"""

import json
import logging
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime

from modules.agent.orchestrator import UnifiedAgentOrchestrator
from modules.tasks.task_manager import PersistentTaskManager

logger = logging.getLogger(__name__)


class AutonomousWorkflowEngine:
    """Orchestrates long-running, goal-driven autonomous tasks."""

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

    async def _run_goal_pipeline(self, task_id: str, goal: str):
        """Pipeline executing the decomposed subtasks with live cancellation checking."""
        logger.info(f"Starting pipeline execution for task {task_id}: {goal}")
        try:
            if self.task_manager.is_cancelled(task_id):
                return

            # Step 1: Decompose Goal
            self.task_manager.update_progress(
                task_id=task_id,
                step_desc="Decomposing goal into actionable plan",
                steps_completed=1,
                total_steps=5
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

            # Step 2: Execute First Subtask
            self.task_manager.update_progress(
                task_id=task_id,
                step_desc=f"Executing: {steps[0]}",
                steps_completed=2,
                total_steps=5,
                checkpoint={"plan": steps, "current_step": 0}
            )
            step1_out = await self.orchestrator.execute_task(
                query=f"Autonomous Goal: {goal}. Subtask 1: {steps[0]}",
                conversation_history=[]
            )

            if self.task_manager.is_cancelled(task_id):
                return

            # Step 3: Execute Second Subtask
            step2_desc = steps[1] if len(steps) > 1 else "Execution and data compilation"
            self.task_manager.update_progress(
                task_id=task_id,
                step_desc=f"Executing: {step2_desc}",
                steps_completed=3,
                total_steps=5,
                checkpoint={"plan": steps, "step1_out": step1_out[:300]}
            )
            step2_out = await self.orchestrator.execute_task(
                query=f"Context from previous step:\n{step1_out}\n\nExecute next subtask: {step2_desc}",
                conversation_history=[]
            )

            if self.task_manager.is_cancelled(task_id):
                return

            # Step 4: Execute Third Subtask
            step3_desc = steps[2] if len(steps) > 2 else "Final verification and detail consolidation"
            self.task_manager.update_progress(
                task_id=task_id,
                step_desc=f"Executing: {step3_desc}",
                steps_completed=4,
                total_steps=5,
                checkpoint={"plan": steps, "step2_out": step2_out[:300]}
            )
            step3_out = await self.orchestrator.execute_task(
                query=f"Context from previous steps:\n{step1_out}\n\n{step2_out}\n\nExecute subtask 3: {step3_desc}",
                conversation_history=[]
            )

            if self.task_manager.is_cancelled(task_id):
                return

            # Step 5: Final Synthesis & Completion
            self.task_manager.update_progress(
                task_id=task_id,
                step_desc="Synthesizing final deliverable",
                steps_completed=5,
                total_steps=5
            )
            final_prompt = (
                f"Synthesize the final deliverable for the user's goal: '{goal}'.\n\n"
                f"Findings & Results from all steps:\n"
                f"Step 1 ({steps[0]}):\n{step1_out}\n\n"
                f"Step 2 ({step2_desc}):\n{step2_out}\n\n"
                f"Step 3 ({step3_desc}):\n{step3_out}\n\n"
                "Provide a complete, structured summary with deliverables in British JARVIS tone."
            )
            final_deliverable = await asyncio.to_thread(self.orchestrator.llm.generate, [{"role": "user", "content": final_prompt}], False)

            self.task_manager.complete_task(task_id, final_deliverable)

        except asyncio.CancelledError:
            logger.info(f"Task pipeline [{task_id}] terminated due to user cancellation.")
        except Exception as e:
            logger.error(f"Autonomous workflow {task_id} failed: {e}", exc_info=True)
            self.task_manager.fail_task(task_id, str(e))
