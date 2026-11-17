"""
tests/v2/test_tasks.py — Persistent Background Task Manager Tests
==================================================================
Validates PersistentTaskManager:
  - Task creation, progress tracking, completion, and failure
  - Checkpoint persistence in SQLite
  - Cancellation via asyncio.Event token and DB sync
  - update_progress() raising asyncio.CancelledError on cancelled task
  - recover_interrupted_tasks() transitioning stale RUNNING/QUEUED to INTERRUPTED
"""

import sys
import asyncio
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from modules.tasks.task_manager import PersistentTaskManager, TaskStatus


@pytest.fixture
def tm(tmp_path):
    db_file = tmp_path / "test_tasks.db"
    return PersistentTaskManager(db_path=db_file)


class TestTaskLifecycle:
    def test_create_and_get_task(self, tm):
        task = tm.create_task(title="Data Analysis", goal="Analyze sales data", total_steps=3)
        assert task["task_id"] is not None
        assert task["title"] == "Data Analysis"
        assert task["status"] == TaskStatus.QUEUED

        fetched = tm.get_task(task["task_id"])
        assert fetched is not None
        assert fetched["goal"] == "Analyze sales data"
        assert fetched["progress_pct"] == 0

    def test_update_progress_and_checkpoint(self, tm):
        task = tm.create_task(title="Web Scraping", goal="Scrape docs", total_steps=4)
        tid = task["task_id"]

        tm.update_progress(
            task_id=tid,
            step_desc="Scraped page 1",
            steps_completed=1,
            checkpoint={"last_page": 1}
        )

        fetched = tm.get_task(tid)
        assert fetched["status"] == TaskStatus.RUNNING
        assert fetched["progress_pct"] == 25
        assert fetched["current_step"] == "Scraped page 1"
        assert '"last_page": 1' in fetched["checkpoint_data"]

    def test_complete_task(self, tm):
        task = tm.create_task(title="Build Project", goal="Compile binary")
        tid = task["task_id"]

        tm.complete_task(tid, result_summary="Build succeeded with 0 warnings.")
        fetched = tm.get_task(tid)
        assert fetched["status"] == TaskStatus.COMPLETED
        assert fetched["progress_pct"] == 100
        assert "Build succeeded" in fetched["result_summary"]

    def test_fail_task(self, tm):
        task = tm.create_task(title="Deploy Server", goal="Deploy to cluster")
        tid = task["task_id"]

        tm.fail_task(tid, error_msg="Port 80 already in use")
        fetched = tm.get_task(tid)
        assert fetched["status"] == TaskStatus.FAILED
        assert "Port 80 already in use" in fetched["result_summary"]


class TestCancellation:
    def test_cancel_sets_token_and_status(self, tm):
        task = tm.create_task(title="Long Job", goal="Calculate pi to 1M digits")
        tid = task["task_id"]

        token = tm.get_cancellation_token(tid)
        assert not token.is_set()
        assert not tm.is_cancelled(tid)

        res = tm.cancel_task(tid)
        assert res is True
        assert token.is_set()
        assert tm.is_cancelled(tid)

        fetched = tm.get_task(tid)
        assert fetched["status"] == TaskStatus.CANCELLED

    def test_update_progress_raises_cancelled_error(self, tm):
        task = tm.create_task(title="Cancelled Job", goal="Test abort")
        tid = task["task_id"]

        tm.cancel_task(tid)

        with pytest.raises(asyncio.CancelledError):
            tm.update_progress(tid, "Next step", 1)


class TestCrashRecovery:
    def test_recover_interrupted_tasks(self, tm):
        # Create tasks directly in RUNNING and QUEUED states
        t1 = tm.create_task(title="Running Task", goal="Was mid-execution")
        tm.update_progress(t1["task_id"], "Working", 1, total_steps=2)

        t2 = tm.create_task(title="Queued Task", goal="Was waiting in queue")

        t3 = tm.create_task(title="Done Task", goal="Was finished")
        tm.complete_task(t3["task_id"], "Finished cleanly")

        recovered = tm.recover_interrupted_tasks()
        assert t1["task_id"] in recovered
        assert t2["task_id"] in recovered
        assert t3["task_id"] not in recovered

        f1 = tm.get_task(t1["task_id"])
        assert f1["status"] == TaskStatus.INTERRUPTED
        assert "restart" in f1["current_step"].lower()

        f2 = tm.get_task(t2["task_id"])
        assert f2["status"] == TaskStatus.INTERRUPTED

        f3 = tm.get_task(t3["task_id"])
        assert f3["status"] == TaskStatus.COMPLETED
