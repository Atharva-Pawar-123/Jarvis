"""
modules/tasks/task_manager.py — Persistent Background Task Manager for JARVIS (V2.1 Hardened)
=============================================================================================
Manages long-running asynchronous tasks with:
- Checkpointed state machine stored in SQLite (survives app & PC restarts)
- Live cancellation tokens (asyncio.Event) for responsive thread termination
- Startup recovery: discovers interrupted tasks from unclean shutdown and cleans state
- Subtask DAG progress tracking
- Task inspection and control APIs
"""

import sqlite3
import json
import logging
import asyncio
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional
from pathlib import Path

import config

logger = logging.getLogger(__name__)

TASKS_DB_PATH = config.DATA_DIR / "jarvis_tasks.db"


class TaskStatus:
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    RESUMING = "RESUMING"
    WAITING_APPROVAL = "WAITING_APPROVAL"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    INTERRUPTED = "INTERRUPTED"


class PersistentTaskManager:
    """Stores and coordinates long-running background tasks across restarts."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or TASKS_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        # Active cancellation tokens in-memory: task_id -> asyncio.Event
        self._cancellation_events: Dict[str, asyncio.Event] = {}
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    task_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    goal TEXT NOT NULL,
                    status TEXT NOT NULL,
                    progress_pct INTEGER DEFAULT 0,
                    current_step TEXT DEFAULT '',
                    total_steps INTEGER DEFAULT 1,
                    steps_completed INTEGER DEFAULT 0,
                    checkpoint_data TEXT DEFAULT '{}',
                    result_summary TEXT DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            conn.commit()

    def recover_interrupted_tasks(self) -> List[str]:
        """
        Scans SQLite database upon startup. Any tasks marked RUNNING or QUEUED
        from a previous session are transitioned to INTERRUPTED so they don't linger.
        """
        recovered_ids = []
        now = datetime.now().isoformat()
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT task_id, title FROM tasks WHERE status IN (?, ?)",
                (TaskStatus.RUNNING, TaskStatus.QUEUED)
            ).fetchall()

            for row in rows:
                tid = row["task_id"]
                conn.execute(
                    "UPDATE tasks SET status = ?, current_step = 'Interrupted by system restart', updated_at = ? WHERE task_id = ?",
                    (TaskStatus.INTERRUPTED, now, tid)
                )
                recovered_ids.append(tid)
                logger.info(f"Task recovery: Marked previous task [{tid}] '{row['title']}' as INTERRUPTED.")

            conn.commit()
        return recovered_ids

    def resume_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Transitions an INTERRUPTED, PAUSED, or FAILED task back into RESUMING / QUEUED
        status so that the workflow engine can pick up from its last saved checkpoint.
        """
        now = datetime.now().isoformat()
        with self._get_conn() as conn:
            row = conn.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
            if not row:
                return None

            task_dict = dict(row)
            # Reallocate cancellation token
            self._cancellation_events[task_id] = asyncio.Event()

            conn.execute(
                "UPDATE tasks SET status = ?, current_step = 'Resuming from checkpoint...', updated_at = ? WHERE task_id = ?",
                (TaskStatus.RESUMING, now, task_id)
            )
            conn.commit()

            task_dict["status"] = TaskStatus.RESUMING
            task_dict["current_step"] = "Resuming from checkpoint..."
            logger.info(f"Task [{task_id}] '{task_dict['title']}' transitioned to RESUMING.")
            return task_dict

    def create_task(self, title: str, goal: str, total_steps: int = 1) -> Dict[str, Any]:
        """Creates a new task in the database and assigns a cancellation token."""
        task_id = str(uuid.uuid4())
        now = datetime.now().isoformat()
        with self._get_conn() as conn:
            conn.execute("""
                INSERT INTO tasks (
                    task_id, title, goal, status, progress_pct,
                    current_step, total_steps, steps_completed,
                    checkpoint_data, result_summary, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                task_id, title, goal, TaskStatus.QUEUED, 0,
                "Initialized", total_steps, 0,
                "{}", "", now, now
            ))
            conn.commit()

        # Allocate cancellation event
        self._cancellation_events[task_id] = asyncio.Event()

        logger.info(f"Task created: [{task_id}] {title}")
        return {
            "task_id": task_id,
            "title": title,
            "goal": goal,
            "status": TaskStatus.QUEUED,
            "progress_pct": 0,
            "created_at": now
        }

    def get_cancellation_token(self, task_id: str) -> asyncio.Event:
        """Retrieves or registers an asyncio.Event cancellation token for a task."""
        if task_id not in self._cancellation_events:
            self._cancellation_events[task_id] = asyncio.Event()
        return self._cancellation_events[task_id]

    def is_cancelled(self, task_id: str) -> bool:
        """Fast check to see if cancellation was triggered."""
        token = self._cancellation_events.get(task_id)
        if token and token.is_set():
            return True
        # Check database status as backup
        task = self.get_task(task_id)
        return bool(task and task.get("status") == TaskStatus.CANCELLED)

    def cancel_task(self, task_id: str) -> bool:
        """Sets the in-memory cancellation token and updates database record immediately."""
        now = datetime.now().isoformat()
        token = self._cancellation_events.get(task_id)
        if token:
            token.set()

        with self._get_conn() as conn:
            conn.execute(
                "UPDATE tasks SET status = ?, current_step = 'Cancelled by user', updated_at = ? WHERE task_id = ?",
                (TaskStatus.CANCELLED, now, task_id)
            )
            conn.commit()
        logger.info(f"Task [{task_id}] cancellation requested and signal set.")
        return True

    def update_progress(self, task_id: str, step_desc: str, steps_completed: int, total_steps: Optional[int] = None, checkpoint: Optional[dict] = None):
        """Updates task progress and saves an execution checkpoint if not cancelled."""
        if self.is_cancelled(task_id):
            raise asyncio.CancelledError(f"Task [{task_id}] has been cancelled.")

        now = datetime.now().isoformat()
        with self._get_conn() as conn:
            row = conn.execute("SELECT total_steps FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
            tot = total_steps or (row["total_steps"] if row else 1)
            pct = int((steps_completed / tot) * 100) if tot > 0 else 0
            pct = min(100, max(0, pct))

            checkpoint_str = json.dumps(checkpoint) if checkpoint else "{}"
            conn.execute("""
                UPDATE tasks
                SET current_step = ?, steps_completed = ?, total_steps = ?,
                    progress_pct = ?, checkpoint_data = ?, status = ?, updated_at = ?
                WHERE task_id = ?
            """, (step_desc, steps_completed, tot, pct, checkpoint_str, TaskStatus.RUNNING, now, task_id))
            conn.commit()

    def complete_task(self, task_id: str, result_summary: str):
        """Marks a task as completed with its final output."""
        now = datetime.now().isoformat()
        with self._get_conn() as conn:
            conn.execute("""
                UPDATE tasks
                SET status = ?, progress_pct = 100, current_step = 'Completed',
                    result_summary = ?, updated_at = ?
                WHERE task_id = ?
            """, (TaskStatus.COMPLETED, result_summary, now, task_id))
            conn.commit()
        self._cancellation_events.pop(task_id, None)
        logger.info(f"Task completed: [{task_id}]")

    def fail_task(self, task_id: str, error_msg: str):
        """Marks a task as failed."""
        now = datetime.now().isoformat()
        with self._get_conn() as conn:
            conn.execute("""
                UPDATE tasks
                SET status = ?, current_step = 'Failed',
                    result_summary = ?, updated_at = ?
                WHERE task_id = ?
            """, (TaskStatus.FAILED, f"Error: {error_msg}", now, task_id))
            conn.commit()
        self._cancellation_events.pop(task_id, None)
        logger.error(f"Task failed: [{task_id}] - {error_msg}")

    def list_tasks(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Lists recent tasks."""
        with self._get_conn() as conn:
            rows = conn.execute("SELECT * FROM tasks ORDER BY updated_at DESC LIMIT ?", (limit,)).fetchall()
            return [dict(r) for r in rows]

    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        with self._get_conn() as conn:
            row = conn.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
            return dict(row) if row else None
