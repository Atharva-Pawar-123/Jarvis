"""
server/websocket_manager.py — WebSocket Connection Manager
==========================================================
Manages concurrent WebSocket connections per session, broadcasts
streaming LLM tokens and JARVIS state changes in real time.
"""

import asyncio
import json
import logging
from typing import Dict, List

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections organized by session_id."""

    def __init__(self):
        self.active: Dict[str, List[WebSocket]] = {}  # session_id → [sockets]

    async def connect(self, ws: WebSocket, session_id: str):
        """Accept and register a new WebSocket connection."""
        await ws.accept()
        if session_id not in self.active:
            self.active[session_id] = []
        self.active[session_id].append(ws)
        logger.info(f"WS connected: session={session_id} total={self._total()}")

    def disconnect(self, ws: WebSocket, session_id: str):
        """Remove a WebSocket from the active pool."""
        if session_id in self.active:
            self.active[session_id] = [s for s in self.active[session_id] if s != ws]
            if not self.active[session_id]:
                del self.active[session_id]
        logger.info(f"WS disconnected: session={session_id} total={self._total()}")

    async def broadcast_token(self, token: str):
        """Send a streaming LLM token to ALL connected sessions."""
        dead = []
        for sid, sockets in self.active.items():
            for ws in sockets:
                try:
                    await ws.send_json({"type": "token", "content": token})
                except Exception:
                    dead.append((sid, ws))
        for sid, ws in dead:
            self.disconnect(ws, sid)

    async def broadcast_state(self, state: str):
        """Broadcast JARVIS state change (idle/thinking/speaking) to all."""
        dead = []
        for sid, sockets in self.active.items():
            for ws in sockets:
                try:
                    await ws.send_json({"type": "state", "state": state})
                except Exception:
                    dead.append((sid, ws))
        for sid, ws in dead:
            self.disconnect(ws, sid)

    async def send_to_session(self, session_id: str, data: dict):
        """Send data to all connections in a specific session."""
        if session_id not in self.active:
            return
        dead = []
        for ws in self.active[session_id]:
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws, session_id)

    def _total(self) -> int:
        return sum(len(v) for v in self.active.values())
