"""
modules/autonomous_workflow.py — High-Level Autonomous Goal Execution for JARVIS
===============================================================================
Enables true goal-driven autonomy with:
- Dynamic DAG subtask graph decomposition with dependency awareness
- Concurrent dispatch of independent graph nodes via asyncio
- Resumable checkpoint persistence via PersistentTaskManager
- Live cancellation token propagation to orchestrator & tools
- Synthesizes findings into structured Markdown deliverables
"""

import json
import logging
import asyncio
from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime

from modules.agent.orchestrator import UnifiedAgentOrchestrator
from modules.tasks.task_manager import PersistentTaskManager, TaskStatus

logger = logging.getLogger(__name__)


@dataclass
class DAGNode:
    id: str
    description: str
    dependencies: List[str] = field(default_factory=list)
    status: str = "pending"  # pending, running, completed, failed
    output: Optional[str] = None


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
        """Pipeline executing decomposed subtasks via dependency-aware DAG."""
        logger.info(f"Starting DAG pipeline execution for task {task_id} (resumed={is_resumed}): {goal}")
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

            # Plan or retrieve existing DAG
            raw_nodes = checkpoint.get("dag_nodes", [])
            step_outputs = checkpoint.get("step_outputs", {})

            if not raw_nodes:
                self.task_manager.update_progress(
                    task_id=task_id,
                    step_desc="Decomposing goal into dependency DAG",
                    steps_completed=1,
                    total_steps=6,
                    checkpoint={"dag_nodes": [], "step_outputs": {}}
                )

                plan_prompt = (
                    f"Break this goal into 3 structured subtasks with dependencies: {goal}\n"
                    "Output a JSON list of objects: [{\"id\": \"task1\", \"desc\": \"...\", \"deps\": []}, "
                    "{\"id\": \"task2\", \"desc\": \"...\", \"deps\": [\"task1\"]}, "
                    "{\"id\": \"task3\", \"desc\": \"...\", \"deps\": [\"task2\"]}]"
                )
                raw_plan = await asyncio.to_thread(self.orchestrator.llm.generate, [{"role": "user", "content": plan_prompt}], False)

                raw_nodes = [
                    {"id": "step_1", "desc": "Initial research and inspection", "deps": []},
                    {"id": "step_2", "desc": "Execution and data compilation", "deps": ["step_1"]},
                    {"id": "step_3", "desc": "Final analysis and draft", "deps": ["step_2"]},
                ]
                try:
                    import re
                    match = re.search(r'\[.*\]', raw_plan, re.DOTALL)
                    if match:
                        parsed = json.loads(match.group(0))
                        if isinstance(parsed, list) and len(parsed) >= 1:
                            raw_nodes = []
                            for idx, item in enumerate(parsed[:4]):
                                nid = item.get("id") or f"step_{idx+1}"
                                ndesc = item.get("desc") or item.get("description") or str(item)
                                ndeps = item.get("deps") or item.get("dependencies") or []
                                raw_nodes.append({"id": nid, "desc": ndesc, "deps": ndeps})
                except Exception:
                    pass

            # Construct nodes and strictly validate all dependencies
            nodes: Dict[str, DAGNode] = {}
            all_node_ids = {item["id"] for item in raw_nodes}

            for item in raw_nodes:
                nid = item["id"]
                deps = item.get("deps", [])
                # Strict validation: reject the entire plan if any dependency refers to an undefined node
                for dep in deps:
                    if dep not in all_node_ids:
                        error_msg = f"DAG plan rejected: Node '{nid}' depends on unknown task ID '{dep}'."
                        logger.error(error_msg)
                        self.task_manager.update_progress(
                            task_id=task_id,
                            step_desc=error_msg,
                            steps_completed=0,
                            total_steps=1
                        )
                        raise ValueError(error_msg)

                node = DAGNode(
                    id=nid,
                    description=item["desc"],
                    dependencies=deps
                )
                if nid in step_outputs:
                    node.status = "completed"
                    node.output = step_outputs[nid]
                nodes[nid] = node

            # Validate DAG: detect cycles via topological sort (Kahn's algorithm)
            in_degree = {nid: 0 for nid in nodes}
            for n in nodes.values():
                for dep in n.dependencies:
                    if dep in in_degree:
                        in_degree[n.id] += 1  # n depends on dep, so n has an incoming edge

            topo_queue = [nid for nid, deg in in_degree.items() if deg == 0]
            visited_count = 0
            temp_queue = list(topo_queue)
            while temp_queue:
                current = temp_queue.pop(0)
                visited_count += 1
                for n in nodes.values():
                    if current in n.dependencies:
                        in_degree[n.id] -= 1
                        if in_degree[n.id] == 0:
                            temp_queue.append(n.id)

            if visited_count != len(nodes):
                cycle_nodes = [nid for nid, deg in in_degree.items() if deg > 0]
                error_msg = f"DAG cycle detected among nodes: {cycle_nodes}. Cannot execute."
                logger.error(error_msg)
                self.task_manager.update_progress(
                    task_id=task_id,
                    step_desc=error_msg,
                    steps_completed=0,
                    total_steps=1
                )
                raise RuntimeError(error_msg)

            total_steps = len(nodes) + 2
            completed_count = sum(1 for n in nodes.values() if n.status == "completed")

            # Topological execution loop
            while any(n.status in ("pending", "running") for n in nodes.values()):
                if self.task_manager.is_cancelled(task_id):
                    return

                # Find all ready nodes (all deps completed)
                ready_nodes = [
                    n for n in nodes.values()
                    if n.status == "pending" and all(nodes[dep].status == "completed" for dep in n.dependencies if dep in nodes)
                ]

                if not ready_nodes and any(n.status == "pending" for n in nodes.values()):
                    # True deadlock: pending nodes have failed or stuck dependencies
                    stuck_nodes = [n.id for n in nodes.values() if n.status == "pending"]
                    failed_deps = set()
                    for n in nodes.values():
                        if n.status == "pending":
                            for dep in n.dependencies:
                                if dep in nodes and nodes[dep].status == "failed":
                                    failed_deps.add(dep)
                    error_msg = (
                        f"DAG deadlock: nodes {stuck_nodes} are blocked. "
                        f"Failed dependencies: {list(failed_deps) if failed_deps else 'none (possible cycle or missing dep)'}."
                    )
                    logger.error(error_msg)
                    # Mark all stuck nodes as failed instead of silently unlocking
                    for nid in stuck_nodes:
                        nodes[nid].status = "failed"
                        nodes[nid].output = error_msg
                    break

                for n in ready_nodes:
                    n.status = "running"

                # Helper to execute single node
                async def _exec_node(node: DAGNode):
                    if self.task_manager.is_cancelled(task_id):
                        return
                    dep_contexts = "\n".join([f"[{dep}]: {nodes[dep].output[:300]}" for dep in node.dependencies if dep in nodes and nodes[dep].output])
                    query = f"Autonomous Goal: {goal}\nDependencies Context:\n{dep_contexts}\n\nExecute task node: {node.description}"
                    out = await self.orchestrator.execute_task(
                        query=query,
                        conversation_history=[],
                        cancellation_token=cancel_token
                    )
                    node.output = out
                    node.status = "completed"
                    step_outputs[node.id] = out

                # Execute ready nodes concurrently
                await asyncio.gather(*[_exec_node(n) for n in ready_nodes])

                completed_count = sum(1 for n in nodes.values() if n.status == "completed")
                checkpoint["dag_nodes"] = raw_nodes
                checkpoint["step_outputs"] = step_outputs

                self.task_manager.update_progress(
                    task_id=task_id,
                    step_desc=f"Completed {completed_count}/{len(nodes)} graph tasks",
                    steps_completed=completed_count + 1,
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
                f"Findings & Results from all DAG steps:\n{all_results}\n\n"
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
