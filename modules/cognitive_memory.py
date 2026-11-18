"""
modules/cognitive_memory.py — 4-Tier Cognitive Memory System for JARVIS
========================================================================
1. Working Memory: Transient active context and goals.
2. Episodic Memory: Chronological logs of completed tasks.
3. Semantic Memory: Long-term knowledge base (ChromaDB + BM25).
4. Procedural Memory: User habits, workflow styles, and formatting preferences.
"""

import sqlite3
import json
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from pathlib import Path

import config
from modules.long_term_memory import HybridRAGMemory

logger = logging.getLogger(__name__)

MEMORY_DB_PATH = config.DATA_DIR / "jarvis_advanced_memory.db"


class FourTierMemorySystem:
    """Four-Tier cognitive memory architecture."""

    def __init__(self, hybrid_rag: HybridRAGMemory, db_path: Optional[Path] = None):
        self.rag = hybrid_rag
        self.db_path = db_path or MEMORY_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS procedural_memory (
                    key TEXT PRIMARY KEY,
                    category TEXT NOT NULL,
                    preference TEXT NOT NULL,
                    confidence REAL DEFAULT 1.0,
                    updated_at TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS episodic_memory (
                    episode_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_goal TEXT NOT NULL,
                    outcome TEXT NOT NULL,
                    tools_used TEXT NOT NULL,
                    timestamp TEXT NOT NULL
                )
            """)
            conn.commit()

    # ── Tier 1: Working Memory ──────────────────────────────────────────
    def format_working_context(self, active_session_id: str, active_goal: str = "") -> str:
        """
        Synthesizes active working context across all 4 tiers:
        - Active goal & session constraints
        - Top procedural habits
        - Relevant past episodes to guide execution
        - Semantic memory facts
        """
        context_lines = []

        if active_goal:
            context_lines.append(f"ACTIVE GOAL / TASK: {active_goal}")

        # Inject procedural rules/habits
        procedural = self.get_all_procedural_preferences()
        if procedural:
            context_lines.append("USER PREFERENCES & PROCEDURAL HABITS:")
            for p in procedural[:5]:
                context_lines.append(f"- [{p['category']}] {p['preference']}")

        # Retrieve relevant episodic memory for active goal
        if active_goal:
            recent_episodes = self.get_recent_episodes(limit=3)
            matching_episodes = [
                e for e in recent_episodes
                if any(w.lower() in e["user_goal"].lower() for w in active_goal.split() if len(w) > 3)
            ]
            if matching_episodes:
                context_lines.append("RELEVANT PAST EPISODES & OUTCOMES:")
                for ep in matching_episodes:
                    context_lines.append(f"- Past Goal: '{ep['user_goal']}' -> Outcome: '{ep['outcome'][:150]}'")

        return "\n".join(context_lines)

    # ── Tier 2: Episodic Memory ─────────────────────────────────────────
    def log_episode(self, user_goal: str, outcome: str, tools_used: List[str]):
        now = datetime.now().isoformat()
        with self._get_conn() as conn:
            conn.execute("""
                INSERT INTO episodic_memory (user_goal, outcome, tools_used, timestamp)
                VALUES (?, ?, ?, ?)
            """, (user_goal, outcome, json.dumps(tools_used), now))
            conn.commit()

    def get_recent_episodes(self, limit: int = 5) -> List[Dict[str, Any]]:
        with self._get_conn() as conn:
            rows = conn.execute("SELECT * FROM episodic_memory ORDER BY episode_id DESC LIMIT ?", (limit,)).fetchall()
            return [dict(r) for r in rows]

    # ── Tier 3: Semantic Memory (Hybrid RAG + Importance) ───────────────
    def add_semantic_fact(self, fact: str, category: str = "general", importance: int = 5, expires_at: Optional[str] = None):
        meta = {
            "category": category,
            "importance": importance,
            "timestamp": datetime.now().isoformat(),
            "expires_at": expires_at or ""
        }
        self.rag.add_fact(fact, meta)

    def retrieve_semantic_context(self, query: str) -> str:
        return self.rag.get_relevant_context(query)

    # ── Tier 4: Procedural Memory (Habits & Preferences) ────────────────
    def set_procedural_preference(self, key: str, category: str, preference: str):
        now = datetime.now().isoformat()
        with self._get_conn() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO procedural_memory (key, category, preference, confidence, updated_at)
                VALUES (?, ?, ?, 1.0, ?)
            """, (key, category, preference, now))
            conn.commit()

    def get_all_procedural_preferences(self) -> List[Dict[str, Any]]:
        with self._get_conn() as conn:
            rows = conn.execute("SELECT * FROM procedural_memory ORDER BY category ASC").fetchall()
            return [dict(r) for r in rows]

    def delete_procedural_preference(self, key: str) -> bool:
        with self._get_conn() as conn:
            cur = conn.execute("DELETE FROM procedural_memory WHERE key = ?", (key,))
            conn.commit()
            return cur.rowcount > 0

    def delete_episode(self, episode_id: int) -> bool:
        with self._get_conn() as conn:
            cur = conn.execute("DELETE FROM episodic_memory WHERE episode_id = ?", (episode_id,))
            conn.commit()
            return cur.rowcount > 0

    def get_working_memory_state(self, session_id: Optional[str] = None) -> Dict[str, Any]:
        """Inspects working memory context, active constraints, and procedural habits."""
        procedural = self.get_all_procedural_preferences()
        recent_episodes = self.get_recent_episodes(limit=3)
        return {
            "session_id": session_id or "default",
            "procedural_rules_count": len(procedural),
            "recent_episodes_count": len(recent_episodes),
            "active_rules": [p["preference"] for p in procedural],
            "recent_goals": [e["user_goal"] for e in recent_episodes],
        }
