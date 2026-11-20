"""
modules/image_studio_db.py — Persistent Database for JARVIS Image Studio Pro
============================================================================
Manages visual sessions, assets (generated, uploaded, edited), version lineage,
and library indexing with SQLite.
"""

import sqlite3
import logging
import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

class ImageStudioDB:
    def __init__(self, db_path: str = "data/image_studio.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            conn.execute("PRAGMA journal_mode = WAL")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS visual_sessions (
                    session_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    thumbnail_url TEXT DEFAULT '',
                    mode TEXT DEFAULT 'generate',
                    workspace_state TEXT DEFAULT '{}'
                )
            """)
            # Migration check: add workspace_state column if missing in existing databases
            try:
                conn.execute("ALTER TABLE visual_sessions ADD COLUMN workspace_state TEXT DEFAULT '{}'")
            except sqlite3.OperationalError:
                pass # Already exists
            conn.execute("""
                CREATE TABLE IF NOT EXISTS visual_assets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT,
                    asset_type TEXT NOT NULL, -- 'generated', 'uploaded', 'edited'
                    filepath TEXT NOT NULL,
                    prompt TEXT DEFAULT '',
                    negative_prompt TEXT DEFAULT '',
                    model TEXT DEFAULT '',
                    seed INTEGER DEFAULT 0,
                    parent_asset_id INTEGER DEFAULT NULL,
                    width INTEGER DEFAULT 512,
                    height INTEGER DEFAULT 512,
                    aspect_ratio TEXT DEFAULT '1:1',
                    is_favorite INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES visual_sessions (session_id) ON DELETE SET NULL,
                    FOREIGN KEY (parent_asset_id) REFERENCES visual_assets (id) ON DELETE SET NULL
                )
            """)
            conn.commit()

    def create_session(self, session_id: str, title: str = "New Visual Session", mode: str = "generate") -> Dict[str, Any]:
        now = datetime.datetime.now().isoformat()
        with self._get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO visual_sessions (session_id, title, created_at, updated_at, mode)
                VALUES (?, ?, ?, ?, ?)
            """, (session_id, title, now, now, mode))
            conn.commit()
        return {
            "session_id": session_id,
            "title": title,
            "created_at": now,
            "updated_at": now,
            "thumbnail_url": "",
            "mode": mode,
            "assets": []
        }

    def list_sessions(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.execute("""
                SELECT s.*, 
                       (SELECT filepath FROM visual_assets WHERE session_id = s.session_id ORDER BY id DESC LIMIT 1) as latest_thumb,
                       (SELECT COUNT(*) FROM visual_assets WHERE session_id = s.session_id) as asset_count
                FROM visual_sessions s
                ORDER BY s.updated_at DESC
                LIMIT ?
            """, (limit,))
            rows = cursor.fetchall()
            
            sessions = []
            for r in rows:
                sess = dict(r)
                # Fetch up to 3 thumbnails for Grok Imagine style card reel
                asset_cursor = conn.execute("""
                    SELECT id, filepath, asset_type FROM visual_assets 
                    WHERE session_id = ? ORDER BY id DESC LIMIT 3
                """, (sess["session_id"],))
                sess["thumbnails"] = [dict(a) for a in asset_cursor.fetchall()]
                sessions.append(sess)
            return sessions

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT * FROM visual_sessions WHERE session_id = ?", (session_id,))
            row = cursor.fetchone()
            if not row:
                return None
            sess = dict(row)
            asset_cursor = conn.execute("""
                SELECT * FROM visual_assets WHERE session_id = ? ORDER BY id ASC
            """, (session_id,))
            sess["assets"] = [dict(a) for a in asset_cursor.fetchall()]
            return sess

    def update_session_workspace_state(self, session_id: str, state_dict: Dict[str, Any]) -> bool:
        """Persists current workspace parameters (selected model, prompts, denoise, steps, etc.)"""
        import json
        state_str = json.dumps(state_dict)
        now = datetime.datetime.now().isoformat()
        with self._get_connection() as conn:
            conn.execute("""
                UPDATE visual_sessions 
                SET workspace_state = ?, updated_at = ?
                WHERE session_id = ?
            """, (state_str, now, session_id))
            conn.commit()
            return True

    def delete_session(self, session_id: str, delete_files: bool = True) -> bool:
        with self._get_connection() as conn:
            # First fetch all filepaths associated with this session if file deletion is desired
            if delete_files:
                cursor = conn.execute("SELECT filepath FROM visual_assets WHERE session_id = ?", (session_id,))
                rows = cursor.fetchall()
                for r in rows:
                    fp = r["filepath"]
                    if fp and not fp.startswith("data:"):
                        try:
                            p = Path(fp)
                            if p.exists() and p.is_file():
                                p.unlink(missing_ok=True)
                        except Exception as e:
                            logger.warning(f"Could not delete physical image file {fp}: {e}")

            # Cascade delete visual assets and visual session
            conn.execute("DELETE FROM visual_assets WHERE session_id = ?", (session_id,))
            conn.execute("DELETE FROM visual_sessions WHERE session_id = ?", (session_id,))
            conn.commit()
            return True

    def add_asset(
        self,
        asset_type: str,
        filepath: str,
        session_id: Optional[str] = None,
        prompt: str = "",
        negative_prompt: str = "",
        model: str = "",
        seed: int = 0,
        parent_asset_id: Optional[int] = None,
        width: int = 512,
        height: int = 512,
        aspect_ratio: str = "1:1"
    ) -> Dict[str, Any]:
        now = datetime.datetime.now().isoformat()
        with self._get_connection() as conn:
            cursor = conn.execute("""
                INSERT INTO visual_assets (
                    session_id, asset_type, filepath, prompt, negative_prompt,
                    model, seed, parent_asset_id, width, height, aspect_ratio, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                session_id, asset_type, filepath, prompt, negative_prompt,
                model, seed, parent_asset_id, width, height, aspect_ratio, now
            ))
            asset_id = cursor.lastrowid

            # Update session's updated_at timestamp and thumbnail
            if session_id:
                conn.execute("""
                    UPDATE visual_sessions 
                    SET updated_at = ?, thumbnail_url = ? 
                    WHERE session_id = ?
                """, (now, filepath, session_id))
            conn.commit()

            return {
                "id": asset_id,
                "session_id": session_id,
                "asset_type": asset_type,
                "filepath": filepath,
                "prompt": prompt,
                "negative_prompt": negative_prompt,
                "model": model,
                "seed": seed,
                "parent_asset_id": parent_asset_id,
                "width": width,
                "height": height,
                "aspect_ratio": aspect_ratio,
                "is_favorite": 0,
                "created_at": now
            }

    def list_assets(
        self,
        asset_type: Optional[str] = None,
        favorite_only: bool = False,
        search_query: str = "",
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            query = "SELECT * FROM visual_assets WHERE 1=1"
            params: List[Any] = []

            if asset_type and asset_type != "all":
                query += " AND asset_type = ?"
                params.append(asset_type)

            if favorite_only:
                query += " AND is_favorite = 1"

            if search_query:
                query += " AND (prompt LIKE ? OR filepath LIKE ?)"
                params.extend([f"%{search_query}%", f"%{search_query}%"])

            query += " ORDER BY id DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])

            cursor = conn.execute(query, params)
            return [dict(r) for r in cursor.fetchall()]

    def toggle_favorite(self, asset_id: int) -> bool:
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT is_favorite FROM visual_assets WHERE id = ?", (asset_id,))
            row = cursor.fetchone()
            if not row:
                return False
            new_val = 0 if row["is_favorite"] else 1
            conn.execute("UPDATE visual_assets SET is_favorite = ? WHERE id = ?", (new_val, asset_id))
            conn.commit()
            return bool(new_val)

    def delete_asset(self, asset_id: int, delete_file: bool = True) -> bool:
        with self._get_connection() as conn:
            if delete_file:
                cursor = conn.execute("SELECT filepath FROM visual_assets WHERE id = ?", (asset_id,))
                row = cursor.fetchone()
                if row:
                    fp = row["filepath"]
                    if fp and not fp.startswith("data:"):
                        try:
                            p = Path(fp)
                            if p.exists() and p.is_file():
                                p.unlink(missing_ok=True)
                        except Exception as e:
                            logger.warning(f"Could not delete physical image file {fp}: {e}")

            conn.execute("DELETE FROM visual_assets WHERE id = ?", (asset_id,))
            conn.commit()
            return True
