"""
tests/v2/test_resumable_tasks.py — Checkpoint Resumption & Dynamic Task DAG Tests
================================================================================
Validates:
1. True task resumption from checkpoint data after simulated crash
2. Cancellation token propagation stopping orchestrator loops
3. REST endpoint /api/tasks/{task_id}/resume
"""

import pytest
import asyncio
import json
from unittest.mock import MagicMock, AsyncMock
from fastapi.testclient import TestClient

from modules.tasks.task_manager import PersistentTaskManager, TaskStatus
from modules.autonomous_workflow import AutonomousWorkflowEngine
from modules.agent.orchestrator import UnifiedAgentOrchestrator
from server.api_server import app, get_runtime, LOCAL_AUTH_TOKEN
from server.runtime import JarvisRuntime


@pytest.fixture
def task_manager(tmp_path):
    return PersistentTaskManager(db_path=tmp_path / "test_tasks.db")


def test_task_creation_and_cancellation(task_manager):
    """Verify task lifecycle and instant cancellation token triggering."""
    task = task_manager.create_task("Test Goal", "Perform autonomous search", total_steps=3)
    tid = task["task_id"]

    assert task_manager.is_cancelled(tid) is False

    token = task_manager.get_cancellation_token(tid)
    assert not token.is_set()

    task_manager.cancel_task(tid)
    assert task_manager.is_cancelled(tid) is True
    assert token.is_set()

    # Verify update_progress raises CancelledError on cancelled task
    with pytest.raises(asyncio.CancelledError):
        task_manager.update_progress(tid, "Next step", 1)


def test_recover_and_resume_interrupted_tasks(task_manager):
    """Verify recovering unclean tasks and transitioning them back to RESUMING."""
    task = task_manager.create_task("Crash task", "Simulated run", total_steps=4)
    tid = task["task_id"]

    # Mark as running with intermediate checkpoint
    task_manager.update_progress(
        task_id=tid,
        step_desc="Step 1 complete",
        steps_completed=1,
        total_steps=4,
        checkpoint={"plan": ["A", "B", "C"], "step_outputs": {"step_1": "Result A"}}
    )

    # Simulate restart recovery
    recovered = task_manager.recover_interrupted_tasks()
    assert tid in recovered
    recovered_task = task_manager.get_task(tid)
    assert recovered_task["status"] == TaskStatus.INTERRUPTED

    # Now resume the task
    resumed = task_manager.resume_task(tid)
    assert resumed is not None
    assert resumed["status"] == TaskStatus.RESUMING
    assert task_manager.get_cancellation_token(tid) is not None


@pytest.mark.asyncio
async def test_workflow_engine_resumption_skips_completed_steps(task_manager):
    """Verify that AutonomousWorkflowEngine skips steps already in checkpoint."""
    mock_orchestrator = MagicMock()
    mock_orchestrator.llm = MagicMock()
    mock_orchestrator.execute_task = AsyncMock(return_value="Subtask executed")
    mock_orchestrator.llm.generate.return_value = "Final Summary Deliverable"

    engine = AutonomousWorkflowEngine(mock_orchestrator, task_manager)

    task = task_manager.create_task("Resume Workflow", "Full multi-step task", total_steps=5)
    tid = task["task_id"]

    # Pre-populate checkpoint with step 1 and step 2 already completed
    task_manager.update_progress(
        task_id=tid,
        step_desc="Pre-existing step 2",
        steps_completed=2,
        total_steps=5,
        checkpoint={
            "plan": ["Subtask 1", "Subtask 2", "Subtask 3"],
            "step_outputs": {
                "step_1": "Output 1",
                "step_2": "Output 2"
            }
        }
    )

    # Run resumed pipeline
    await engine._run_goal_pipeline(tid, "Full multi-step task", is_resumed=True)

    # Check only subtask 3 was executed (1 call to execute_task)
    assert mock_orchestrator.execute_task.call_count == 1
    final_task = task_manager.get_task(tid)
    assert final_task["status"] == TaskStatus.COMPLETED
    assert final_task["result_summary"] == "Final Summary Deliverable"


def test_resume_rest_endpoint(tmp_path):
    """Verify POST /api/tasks/{task_id}/resume endpoint."""
    rt = JarvisRuntime()
    tm = PersistentTaskManager(db_path=tmp_path / "api_tasks.db")
    rt.task_manager = tm

    mock_wf = MagicMock()
    mock_wf.resume_goal = AsyncMock(return_value=True)
    rt.workflow_engine = mock_wf

    app.dependency_overrides[get_runtime] = lambda: rt
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {LOCAL_AUTH_TOKEN}"}

    task = tm.create_task("REST Task", "Test endpoint", total_steps=3)
    tid = task["task_id"]

    res = client.post(f"/api/tasks/{tid}/resume", headers=headers)
    assert res.status_code == 200
    assert res.json()["resumed"] == tid

    app.dependency_overrides.clear()
