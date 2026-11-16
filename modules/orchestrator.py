import logging
import threading
import queue
import time
from typing import List, Dict, Any

from modules.llm import IntelligentLLMEngine as LLMEngine
from modules.memory import ConversationMemory

logger = logging.getLogger(__name__)

class WorkerAgent(threading.Thread):
    """A background worker agent that can execute a specific sub-task."""
    def __init__(self, task_id: int, task_description: str, llm: LLMEngine, result_queue: queue.Queue):
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
            # We assume blocking generation for background workers
            result = self.llm.generate(messages, stream=False)
            logger.info(f"[Worker {self.task_id}] Completed task.")
            self.result_queue.put({"task_id": self.task_id, "status": "success", "result": result})
        except Exception as e:
            logger.error(f"[Worker {self.task_id}] Failed: {e}")
            self.result_queue.put({"task_id": self.task_id, "status": "error", "error": str(e)})


class Orchestrator:
    """
    The main Multi-Agent Coordinator.
    Breaks down complex goals into sub-tasks, dispatches them to workers, and synthesizes the results.
    """
    def __init__(self, llm: LLMEngine):
        self.llm = llm

    def execute_complex_goal(self, goal: str) -> str:
        """
        Takes a complex user goal, breaks it down, runs workers, and returns the final synthesis.
        """
        logger.info(f"Orchestrator received complex goal: {goal}")
        
        # Step 1: Breakdown the goal
        plan_prompt = (
            "You are an Orchestrator AI. The user has given you a complex goal. "
            "Break this goal down into 1 to 3 distinct sub-tasks that can be executed independently. "
            "Output ONLY the sub-tasks, one per line, starting with a dash (-)."
            f"\n\nUser Goal: {goal}"
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
            tasks = [goal] # Fallback to doing it as one task
            
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
        synthesis_prompt = "You are the primary JARVIS AI. Synthesize the findings of your sub-agents into a cohesive, final response to the user. Address the user as 'Sir' or 'Boss'.\n\n"
        synthesis_prompt += f"Original Goal: {goal}\n\nSub-Agent Findings:\n"
        
        for r in results:
            if r['status'] == 'success':
                synthesis_prompt += f"Task {r['task_id']} Result: {r['result']}\n\n"
            else:
                synthesis_prompt += f"Task {r['task_id']} Failed: {r['error']}\n\n"
                
        synthesis_messages = [
            {"role": "system", "content": "You are JARVIS. Synthesize worker findings into a final polite response."},
            {"role": "user", "content": synthesis_prompt}
        ]
        
        final_answer = self.llm.generate(synthesis_messages, stream=False)
        return final_answer
