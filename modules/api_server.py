"""
modules/api_server.py — JARVIS On-Demand Web Server
===================================================
Provides a FastAPI-based WebSocket and REST server that only runs when
requested. Includes an auto-shutdown mechanism if no clients are connected
for more than 60 seconds.
"""

import asyncio
import json
import logging
import queue
import threading
import time
from typing import List, Optional

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from pathlib import Path

import config

logger = logging.getLogger(__name__)

class HUDServer:
    def __init__(self):
        self.app = FastAPI()
        self.active_connections: List[WebSocket] = []
        self._server_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._last_activity = time.time()
        self._is_running = False
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        # Thread-safe queue for typed commands from the HUD
        self.command_queue: queue.Queue = queue.Queue()
        
        self._setup_routes()
        self._mount_static()

    def _setup_routes(self):
        @self.app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            await websocket.accept()
            self.active_connections.append(websocket)
            logger.info(f"HUD Client connected. Active: {len(self.active_connections)}")
            self._last_activity = time.time()
            try:
                while True:
                    # Keep alive and wait for client messages (if any)
                    _ = await websocket.receive_text()
                    self._last_activity = time.time()
            except WebSocketDisconnect:
                self.active_connections.remove(websocket)
                logger.info(f"HUD Client disconnected. Remaining: {len(self.active_connections)}")
                self._last_activity = time.time()

        @self.app.get("/api/health")
        def health():
            return {"status": "online", "timestamp": time.time()}

        @self.app.post("/api/command")
        async def send_command(body: dict):
            """Accept a typed command from the HUD UI and enqueue it for JARVIS."""
            text = body.get("text", "").strip()
            if text:
                self.command_queue.put(text)
                logger.info(f"HUD typed command queued: {text!r}")
            return {"status": "ok"}

        @self.app.post("/api/mute")
        async def toggle_mute():
            """Expose mute toggle to HUD button (if wired via main.py)."""
            # Puts a special sentinel into the command queue
            self.command_queue.put("__TOGGLE_MUTE__")
            return {"status": "ok"}

    def _mount_static(self):
        # Mount the HUD directory to serve the frontend
        hud_dir = Path(config.BASE_DIR) / "hud"
        if hud_dir.exists():
            self.app.mount("/", StaticFiles(directory=str(hud_dir), html=True), name="hud")
        else:
            logger.warning(f"HUD directory not found at {hud_dir}")

    async def broadcast(self, data: dict):
        if not self.active_connections:
            return
            
        logger.debug(f"Broadcasting to HUD: {data.get('type') or 'data'}")
            
        message = json.dumps(data)
        dead_connections = []
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception:
                dead_connections.append(connection)
        
        for dead in dead_connections:
            if dead in self.active_connections:
                self.active_connections.remove(dead)

    def _run_uvicorn(self, host: str, port: int):
        logger.info(f"Starting HUD Server on {host}:{port}")
        self._is_running = True
        config_uv = uvicorn.Config(self.app, host=host, port=port, log_level="error")
        server = uvicorn.Server(config_uv)
        
        # We wrap uvicorn's serve in a way we can stop it
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self.loop = loop  # Capture the loop for thread-safe access
        
        # Background task for auto-shutdown check
        async def monitor_inactivity():
            while not self._stop_event.is_set():
                await asyncio.sleep(10)
                if len(self.active_connections) == 0:
                    idle_time = time.time() - self._last_activity
                    if idle_time > 300: # 5 minute timeout
                        logger.info("HUD Server inactive for 300s. Triggering auto-shutdown.")
                        self._stop_event.set()
            
            # Stop uvicorn
            server.should_exit = True
            logger.info("Uvicorn server shutting down...")

        loop.create_task(monitor_inactivity())
        loop.run_until_complete(server.serve())
        self._is_running = False
        logger.info("HUD Server thread terminated.")

    def start(self, host="127.0.0.1", port=8080):
        if self._is_running:
            return False
            
        self._stop_event.clear()
        self._last_activity = time.time()
        self._server_thread = threading.Thread(
            target=self._run_uvicorn, 
            args=(host, port), 
            daemon=True
        )
        self._server_thread.start()
        return True

    def stop(self):
        if self._is_running:
            self._stop_event.set()
            return True
        return False

    def emit(self, data: dict):
        """Thread-safe way to broadcast from synchronous code."""
        if self.is_running() and self.loop:
            asyncio.run_coroutine_threadsafe(self.broadcast(data), self.loop)

    def is_running(self):
        return self._is_running

# Global instance
hud_server = HUDServer()
