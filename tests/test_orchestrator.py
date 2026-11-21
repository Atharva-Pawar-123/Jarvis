import unittest
import queue
from unittest.mock import MagicMock
from modules.ultraplan import UltraPlanCoordinator, WorkerAgent

class DummyLLM:
    PRIMARY_MODEL = "test-model"

    def generate(self, messages, stream=False):
        # Always return a dummy response
        return "Dummy task completed."

    def _generate_blocking(self, messages, model=None):
        return self.generate(messages, stream=False)

class TestOrchestrator(unittest.TestCase):
    def test_worker_agent(self):
        q = queue.Queue()
        llm = DummyLLM()
        worker = WorkerAgent(task_id=1, task_description="Test task", llm=llm, result_queue=q)
        worker.start()
        worker.join()
        
        result = q.get()
        self.assertEqual(result['task_id'], 1)
        self.assertEqual(result['status'], "success")
        self.assertEqual(result['result'], "Dummy task completed.")

    def test_orchestrator_coordinator(self):
        llm = DummyLLM()
        llm.generate = MagicMock(side_effect=[
            "- Task 1\n- Task 2", # Breakdown phase
            "Worker task 1 result", # Worker 1
            "Worker task 2 result", # Worker 2
            "Final Synthesis Result" # Synthesis phase
        ])
        
        # Test the coordinator (we patch notify to avoid spam)
        coord = UltraPlanCoordinator(llm_engine=llm, tts_callback=None, hud_callback=None)
        coord._notify = MagicMock()
        coord._notify_final_result = MagicMock()
        
        coord._run_multi_agent_swarm("Do a complex task")
        
        # Verify synthesis was called
        coord._notify_final_result.assert_called_with("Final Synthesis Result")

if __name__ == '__main__':
    unittest.main()
