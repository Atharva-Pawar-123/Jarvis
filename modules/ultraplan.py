import logging
import threading
import queue
import time
from typing import Any, Callable

logger = logging.getLogger(__name__)

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
            result = self.llm.generate(messages, stream=False)
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
            # Step 1: Breakdown the goal
            plan_prompt = (
                "You are an Orchestrator AI. The user has given you a complex goal. "
                "Break this goal down into 1 to 3 distinct sub-tasks that can be executed independently in parallel. "
                "Output ONLY the sub-tasks, one per line, starting with a dash (-)."
                f"\n\nUser Goal: {query}"
            )
            
            plan_response = self.llm.generate([{"role": "user", "content": plan_prompt}], stream=False)
            
            # Parse tasks
            tasks = []
            if isinstance(plan_response, str):
                for line in plan_response.split('\n'):
                    line = line.strip()
                    if line.startswith('-'):
                        tasks.append(line.lstrip('- ').strip())
            
            if not tasks:
                tasks = [query] # Fallback to single task
                
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
            
            final_result = self.llm.generate(synthesis_messages, stream=False)

            # Complete
            self._notify("Sir, the Multi-Agent Orchestrator session is complete.")
            self._notify_final_result(final_result)

        except Exception as exc:
            logger.error(f"ULTRAPLAN failed: {exc}")
            self._notify("I encountered an error during the orchestration session.")

    def _notify(self, message: str):
        logger.info(f"ULTRAPLAN: {message}")
        if self.tts_callback:
            self.tts_callback(message)
            
    def _notify_final_result(self, result: str):
        logger.info(f"ULTRAPLAN RESULT:\n{result}")
        if self.hud_callback:
            self.hud_callback({
                "type": "ultraplan_result",
                "result": result
            })
        if self.tts_callback:
            self.tts_callback("I have sent the comprehensive results to your HUD and terminal, sir.")
            print(f"\n[ULTRAPLAN RESULT]\n{result}\n")
