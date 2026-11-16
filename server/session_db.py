"""
server/session_db.py — Persistent SQLite Session Store for JARVIS
=================================================================
Stores conversations, messages, titles, and timestamps in SQLite
to ensure conversation context survives application and backend restarts.
"""

import sqlite3
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Any

import config

logger = logging.getLogger(__name__)

DB_PATH = config.DATA_DIR / "jarvis_sessions.db"


class SessionDatabase:
    """Manages SQLite storage for conversation sessions and messages."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """Creates sessions and messages tables if they do not exist."""
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    metadata_json TEXT DEFAULT '{}',
                    FOREIGN KEY(session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id)")
            conn.commit()

    def create_session(self, session_id: str, title: str = "New conversation") -> Dict[str, Any]:
        now = datetime.now().isoformat()
        with self._get_connection() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO sessions (session_id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
                (session_id, title, now, now)
            )
            conn.commit()
        return {"session_id": session_id, "title": title, "created_at": now}

    def update_title(self, session_id: str, title: str):
        with self._get_connection() as conn:
            conn.execute("UPDATE sessions SET title = ?, updated_at = ? WHERE session_id = ?",
                         (title, datetime.now().isoformat(), session_id))
            conn.commit()

    def add_message(self, session_id: str, role: str, content: str, metadata: Optional[dict] = None) -> Dict[str, Any]:
        self.create_session(session_id)
        now = datetime.now().isoformat()
        meta_str = json.dumps(metadata or {})
        with self._get_connection() as conn:
            cursor = conn.execute(
                "INSERT INTO messages (session_id, role, content, timestamp, metadata_json) VALUES (?, ?, ?, ?, ?)",
                (session_id, role, content, now, meta_str)
            )
            conn.execute("UPDATE sessions SET updated_at = ? WHERE session_id = ?", (now, session_id))
            conn.commit()
            msg_id = cursor.lastrowid

        return {
            "id": msg_id,
            "session_id": session_id,
            "role": role,
            "content": content,
            "timestamp": now,
            "metadata": metadata or {}
        }

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            s_row = conn.execute("SELECT * FROM sessions WHERE session_id = ?", (session_id,)).fetchone()
            if not s_row:
                return None
            m_rows = conn.execute(
                "SELECT role, content, timestamp, metadata_json FROM messages WHERE session_id = ? ORDER BY id ASC",
                (session_id,)
            ).fetchall()

            messages = []
            for r in m_rows:
                messages.append({
                    "role": r["role"],
                    "content": r["content"],
                    "timestamp": r["timestamp"],
                    "metadata": json.loads(r["metadata_json"] or "{}")
                })

            return {
                "session_id": s_row["session_id"],
                "title": s_row["title"],
                "created_at": s_row["created_at"],
                "updated_at": s_row["updated_at"],
                "messages": messages
            }

    def list_sessions(self) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            rows = conn.execute("""
                SELECT s.session_id, s.title, s.created_at, s.updated_at,
                       COUNT(m.id) as message_count,
                       (SELECT content FROM messages WHERE session_id = s.session_id ORDER BY id DESC LIMIT 1) as last_message
                FROM sessions s
                LEFT JOIN messages m ON s.session_id = m.session_id
                GROUP BY s.session_id
                ORDER BY s.updated_at DESC
            """).fetchall()

            result = []
            for r in rows:
                result.append({
                    "session_id": r["session_id"],
                    "title": r["title"],
                    "created_at": r["created_at"],
                    "updated_at": r["updated_at"],
                    "message_count": r["message_count"],
                    "last_message": (r["last_message"] or "")[:100]
                })
            return result

    def delete_session(self, session_id: str) -> bool:
        with self._get_connection() as conn:
            conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
            conn.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
            conn.commit()
        return True
