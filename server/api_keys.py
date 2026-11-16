"""
server/api_keys.py — API Key Manager (SQLite)
==============================================
Secure API key management with hashed storage, rate limiting,
and usage tracking — all backed by SQLite for crash safety.
"""

import hashlib
import logging
import secrets
import sqlite3
import time
from pathlib import Path
from typing import Optional, List

logger = logging.getLogger(__name__)

DB_PATH = Path("D:/JARVIS/data/jarvis_data.sqlite")


class APIKeyManager:
    """Manages JARVIS API keys with SQLite persistence."""

    PREFIX = "jv_live_"

    def __init__(self):
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_tables()
        logger.info("APIKeyManager initialized (SQLite).")

    def _init_tables(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS api_keys (
                key_id        TEXT PRIMARY KEY,
                key_hash      TEXT NOT NULL,
                name          TEXT NOT NULL,
                permissions   TEXT NOT NULL DEFAULT '["chat","tools"]',
                rate_limit    INTEGER NOT NULL DEFAULT 100,
                created_at    REAL NOT NULL,
                last_used     REAL,
                usage_count   INTEGER NOT NULL DEFAULT 0,
                active        INTEGER NOT NULL DEFAULT 1,
                usage_this_hour   INTEGER NOT NULL DEFAULT 0,
                hour_window_start REAL NOT NULL
            )
        """)
        self.conn.commit()

    # ── CREATE ──────────────────────────────────────────────────────────
    def create_key(self, name: str, permissions: list,
                   rate_limit: int = 100) -> dict:
        """Create a new API key. Returns the raw key (shown only once)."""
        import json
        raw_key = self.PREFIX + secrets.token_urlsafe(32)
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        key_id = secrets.token_hex(8)
        now = time.time()

        self.conn.execute(
            """INSERT INTO api_keys
               (key_id, key_hash, name, permissions, rate_limit,
                created_at, last_used, usage_count, active,
                usage_this_hour, hour_window_start)
               VALUES (?, ?, ?, ?, ?, ?, NULL, 0, 1, 0, ?)""",
            (key_id, key_hash, name, json.dumps(permissions),
             rate_limit, now, now)
        )
        self.conn.commit()
        logger.info(f"API key created: name={name} id={key_id}")
        return {"key": raw_key, "key_id": key_id, "name": name,
                "created_at": now}

    # ── VALIDATE ────────────────────────────────────────────────────────
    def validate_key(self, raw_key: str) -> Optional[dict]:
        """Validate a raw API key. Returns key data or None."""
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        row = self.conn.execute(
            "SELECT * FROM api_keys WHERE key_hash = ? AND active = 1",
            (key_hash,)
        ).fetchone()

        if not row:
            return None

        now = time.time()
        # Reset hourly window
        if now - row["hour_window_start"] > 3600:
            self.conn.execute(
                """UPDATE api_keys SET usage_this_hour = 0,
                   hour_window_start = ? WHERE key_id = ?""",
                (now, row["key_id"])
            )
            self.conn.commit()
            current_usage = 0
        else:
            current_usage = row["usage_this_hour"]

        # Rate limit check
        if current_usage >= row["rate_limit"]:
            return None  # Rate limited

        # Increment usage
        self.conn.execute(
            """UPDATE api_keys SET
               usage_this_hour = usage_this_hour + 1,
               usage_count = usage_count + 1,
               last_used = ?
               WHERE key_id = ?""",
            (now, row["key_id"])
        )
        self.conn.commit()
        return dict(row)

    # ── REVOKE ──────────────────────────────────────────────────────────
    def revoke_key(self, key_id: str) -> bool:
        cursor = self.conn.execute(
            "UPDATE api_keys SET active = 0 WHERE key_id = ?",
            (key_id,)
        )
        self.conn.commit()
        return cursor.rowcount > 0

    # ── ROTATE ──────────────────────────────────────────────────────────
    def rotate_key(self, key_id: str) -> Optional[dict]:
        """Revoke old key and create a new one with the same name/perms."""
        import json
        row = self.conn.execute(
            "SELECT * FROM api_keys WHERE key_id = ?", (key_id,)
        ).fetchone()
        if not row:
            return None
        self.revoke_key(key_id)
        return self.create_key(
            row["name"],
            json.loads(row["permissions"]),
            row["rate_limit"]
        )

    # ── LIST ────────────────────────────────────────────────────────────
    def list_keys(self) -> list:
        import json
        rows = self.conn.execute(
            "SELECT * FROM api_keys ORDER BY created_at DESC"
        ).fetchall()
        result = []
        for r in rows:
            result.append({
                "key_id": r["key_id"],
                "name": r["name"],
                "permissions": json.loads(r["permissions"]),
                "rate_limit": r["rate_limit"],
                "created_at": r["created_at"],
                "last_used": r["last_used"],
                "usage_count": r["usage_count"],
                "active": bool(r["active"]),
            })
        return result

    # ── STATS ───────────────────────────────────────────────────────────
    def get_usage_stats(self) -> dict:
        rows = self.conn.execute("SELECT * FROM api_keys").fetchall()
        total = sum(r["usage_count"] for r in rows)
        active = sum(1 for r in rows if r["active"])
        return {
            "total_keys": len(rows),
            "active_keys": active,
            "total_api_calls": total,
        }
