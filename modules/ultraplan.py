import logging
import threading
import queue
from typing import Any, Callable, List
from pydantic import BaseModel, Field
import instructor
from openai import OpenAI

import config

logger = logging.getLogger(__name__)

class TaskPlan(BaseModel):
    sub_tasks: List[str] = Field(..., description="A list of distinct, independent sub-tasks to accomplish the goal.")

class WorkerAgent(threading.Thread):
    """A background worker agent that can execute a specific sub-task."""
    def __init__(self, task_id: int, task_description: str, llm: Any, result_queue: queue.Queue):
        super().__init__()
        self.task_id = task_id
        self.task_description = task_description
        self.llm = llm
        self.result_queue = result_queue
        self.daemon = True

    def run(self):
        logger.info(f"[Worker {self.task_id}] Starting task: {self.task_description}")
        
        messages = [
            {"role": "system", "content": "You are a specialized worker agent. Execute the following sub-task diligently and provide a concise report of your findings or actions."},
            {"role": "user", "content": self.task_description}
        ]
        
        try:
            # We use the blocking generation method since workers run in background
            result = self.llm._generate_blocking(messages, self.llm.PRIMARY_MODEL)
            logger.info(f"[Worker {self.task_id}] Completed task.")
            self.result_queue.put({"task_id": self.task_id, "status": "success", "result": result})
        except Exception as e:
            logger.error(f"[Worker {self.task_id}] Failed: {e}")
            self.result_queue.put({"task_id": self.task_id, "status": "error", "error": str(e)})

class UltraPlanCoordinator:
    """
    ULTRAPLAN: Multi-Agent Coordinator.
    Breaks down complex goals into sub-tasks, dispatches them to parallel workers, and synthesizes the results.
    """
    def __init__(self, llm_engine: Any, tts_callback: Callable, hud_callback: Callable):
        self.llm = llm_engine
        self.tts_callback = tts_callback
        self.hud_callback = hud_callback
        
        # Initialize instructor for guaranteed JSON output from Ollama
        self.instructor_client = instructor.from_openai(
            OpenAI(
                base_url=f"{config.OLLAMA_HOST}/v1",
                api_key="ollama"
            ),
            mode=instructor.Mode.JSON
        )

    def execute_plan_async(self, user_query: str):
        """Spawns a background thread so the main JARVIS loop isn't blocked."""
        threading.Thread(
            target=self._run_multi_agent_swarm, 
            args=(user_query,),
            daemon=True
        ).start()

    def _run_multi_agent_swarm(self, query: str):
        self._notify("Sir, I am spinning up the Multi-Agent Orchestrator. This may take a moment.")
        try:
            # Step 1: Breakdown the goal using instructor for strict JSON compliance
            plan_prompt = (
                "You are an Orchestrator AI. The user has given you a complex goal. "
                "Break this goal down into 1 to 3 distinct sub-tasks that can be executed independently in parallel."
                f"\n\nUser Goal: {query}"
            )
            
            try:
                plan = self.instructor_client.chat.completions.create(
                    model=self.llm.PRIMARY_MODEL,
                    response_model=TaskPlan,
                    messages=[
                        {"role": "user", "content": plan_prompt}
                    ]
                )
                tasks = plan.sub_tasks
            except Exception as e:
                logger.error(f"Instructor JSON parsing failed: {e}")
                tasks = [query] # Fallback to single task if instructor fails
                
            if not tasks:
                tasks = [query]
                
            logger.info(f"Orchestrator identified {len(tasks)} sub-tasks: {tasks}")
            
            # Step 2: Spawn Workers
            result_queue = queue.Queue()
            workers = []
            for i, task in enumerate(tasks):
                worker = WorkerAgent(task_id=i+1, task_description=task, llm=self.llm, result_queue=result_queue)
                workers.append(worker)
                worker.start()
                
            # Step 3: Wait for results
            for worker in workers:
                worker.join(timeout=30.0) # 30s timeout per worker
                
            results = []
            while not result_queue.empty():
                results.append(result_queue.get())
                
            # Step 4: Synthesize
            synthesis_prompt = "You are the primary JARVIS AI. Synthesize the findings of your parallel sub-agents into a cohesive, final response to the user.\n\n"
            synthesis_prompt += f"Original Goal: {query}\n\nSub-Agent Findings:\n"
            
            for r in results:
                if r['status'] == 'success':
                    synthesis_prompt += f"Task {r['task_id']} Result: {r['result']}\n\n"
                else:
                    synthesis_prompt += f"Task {r['task_id']} Failed: {r['error']}\n\n"
                    
            synthesis_messages = [
                {"role": "system", "content": "You are JARVIS. Synthesize worker findings into a final response."},
                {"role": "user", "content": synthesis_prompt}
            ]
            
            final_result = self.llm._generate_blocking(synthesis_messages, self.llm.PRIMARY_MODEL)

            # Complete
            self._notify("Sir, the Multi-Agent Orchestrator session is complete.")
            self._notify_final_result(final_result)

        except Exception as exc:
            logger.error(f"ULTRAPLAN failed: {exc}")
            self._notify("I encountered an error during the orchestration session.")

    def _notify(self, message: str):
        logger.info(f"ULTRAPLAN: {message}")
        if self.tts_callback:
            self.tts_callback(message, blocking=False)
            
    def _notify_final_result(self, result: str):
        logger.info(f"ULTRAPLAN RESULT:\n{result}")
        if self.hud_callback:
            self.hud_callback({
                "type": "ultraplan_result",
                "result": result
            })
        if self.tts_callback:
            self.tts_callback("I have sent the comprehensive results to your HUD and terminal, sir.", blocking=True)
            print(f"\n[ULTRAPLAN RESULT]\n{result}\n")
