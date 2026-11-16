"""
modules/mcp/client.py — JARVIS MCP Client
==========================================
Implements the Model Context Protocol (MCP) client.
Communicates with MCP servers over stdio (subprocess) or HTTP/SSE transports
using the JSON-RPC 2.0 message format.

Lifecycle:
    1. Spawn server subprocess (stdio) or connect to HTTP endpoint.
    2. Send `initialize` handshake.
    3. Retrieve `tools/list` to discover available tools.
    4. Invoke tools via `tools/call` on demand.
    5. Cleanly shut down on exit.
"""

import json
import logging
import subprocess
import threading
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# JSON-RPC helpers
# ---------------------------------------------------------------------------

_REQUEST_ID = 0


def _next_id() -> int:
    global _REQUEST_ID
    _REQUEST_ID += 1
    return _REQUEST_ID


def _jsonrpc_request(method: str, params: Optional[Dict] = None, req_id: Optional[int] = None) -> str:
    """Build a JSON-RPC 2.0 request string."""
    if req_id is None:
        req_id = _next_id()
    msg = {"jsonrpc": "2.0", "id": req_id, "method": method}
    if params is not None:
        msg["params"] = params
    return json.dumps(msg) + "\n"


def _jsonrpc_notification(method: str, params: Optional[Dict] = None) -> str:
    """Build a JSON-RPC 2.0 notification (no id, no response expected)."""
    msg = {"jsonrpc": "2.0", "method": method}
    if params is not None:
        msg["params"] = params
    return json.dumps(msg) + "\n"


# ---------------------------------------------------------------------------
# MCP Tool schema (what we expose to the LLM)
# ---------------------------------------------------------------------------

class MCPTool:
    """Represents a single tool exposed by an MCP server."""
    __slots__ = ("name", "description", "input_schema", "server_name")

    def __init__(self, name: str, description: str, input_schema: Dict, server_name: str):
        self.name = name
        self.description = description
        self.input_schema = input_schema
        self.server_name = server_name

    def to_llm_schema(self) -> Dict:
        """Convert to the schema format expected by the LLM tool-calling API."""
        return {
            "name": f"mcp__{self.server_name}__{self.name}",
            "description": f"[MCP:{self.server_name}] {self.description}",
            "parameters": self.input_schema,
        }

    def __repr__(self) -> str:
        return f"MCPTool({self.server_name}/{self.name})"


# ---------------------------------------------------------------------------
# Stdio Transport — communicates with a local subprocess
# ---------------------------------------------------------------------------

class StdioTransport:
    """
    Manages a child process running an MCP server over stdin/stdout.
    Messages are newline-delimited JSON-RPC.
    """

    def __init__(self, command: str, args: List[str], env: Optional[Dict[str, str]] = None):
        self.command = command
        self.args = args
        self.env = env
        self.process: Optional[subprocess.Popen] = None
        self._lock = threading.Lock()

    def start(self) -> None:
        """Launch the subprocess."""
        full_cmd = [self.command] + self.args
        merged_env = None
        if self.env:
            import os
            merged_env = {**os.environ, **self.env}

        try:
            self.process = subprocess.Popen(
                full_cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=merged_env,
                text=True,
                bufsize=1,  # line-buffered
            )
            logger.info(f"MCP stdio process started: {' '.join(full_cmd)} (PID {self.process.pid})")
            
            # Drain stderr in a background thread to prevent deadlocks
            self._stderr_thread = threading.Thread(
                target=self._drain_stderr, daemon=True,
                name=f"mcp-stderr-{self.process.pid}"
            )
            self._stderr_thread.start()
        except FileNotFoundError:
            logger.error(f"MCP server command not found: {self.command}")
            raise
        except Exception as exc:
            logger.error(f"Failed to start MCP server subprocess: {exc}")
            raise

    def send(self, message: str) -> None:
        """Write a JSON-RPC message to the server's stdin."""
        with self._lock:
            if self.process and self.process.stdin:
                try:
                    self.process.stdin.write(message)
                    self.process.stdin.flush()
                except (BrokenPipeError, OSError) as exc:
                    logger.error(f"Failed to write to MCP server stdin: {exc}")

    def receive(self, timeout: float = 10.0) -> Optional[Dict]:
        """Read one JSON-RPC response line from the server's stdout."""
        if not self.process or not self.process.stdout:
            return None

        # Use a thread to read with timeout
        result = [None]

        def _reader():
            try:
                line = self.process.stdout.readline()
                if line:
                    result[0] = json.loads(line.strip())
            except (json.JSONDecodeError, ValueError) as exc:
                logger.warning(f"MCP server sent invalid JSON: {exc}")
            except Exception as exc:
                logger.warning(f"MCP stdout read error: {exc}")

        reader_thread = threading.Thread(target=_reader, daemon=True)
        reader_thread.start()
        reader_thread.join(timeout=timeout)

        if reader_thread.is_alive():
            logger.warning("MCP server response timed out.")
            return None

        return result[0]

    def stop(self) -> None:
        """Terminate the subprocess."""
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=5)
                logger.info(f"MCP stdio process stopped (PID {self.process.pid}).")
            except subprocess.TimeoutExpired:
                self.process.kill()
                logger.warning("MCP server process killed after timeout.")
            except Exception as exc:
                logger.warning(f"Error stopping MCP server: {exc}")
            finally:
                self.process = None

    @property
    def is_alive(self) -> bool:
        return self.process is not None and self.process.poll() is None

    def _drain_stderr(self) -> None:
        """Continuously read stderr so the pipe buffer never fills up (preventing deadlock)."""
        try:
            while self.process and self.process.stderr:
                line = self.process.stderr.readline()
                if not line:
                    break
                logger.debug(f"MCP stderr [{self.command}]: {line.rstrip()}")
        except Exception:
            pass


# ---------------------------------------------------------------------------
# HTTP/SSE Transport — connects to a remote MCP server
# ---------------------------------------------------------------------------

class HttpTransport:
    """
    Connects to an MCP server over HTTP (JSON-RPC POST).
    SSE streaming is not yet implemented — this handles basic request/response.
    """

    def __init__(self, url: str, headers: Optional[Dict[str, str]] = None):
        self.url = url.rstrip("/")
        self.headers = headers or {}

    def start(self) -> None:
        """No startup needed for HTTP, but we verify the endpoint is reachable."""
        import requests as req_lib
        try:
            resp = req_lib.get(self.url, timeout=5, headers=self.headers)
            logger.info(f"MCP HTTP server reachable at {self.url} (status={resp.status_code})")
        except Exception as exc:
            logger.warning(f"MCP HTTP server at {self.url} may be unreachable: {exc}")

    def send_and_receive(self, message: str, timeout: float = 15.0) -> Optional[Dict]:
        """Send a JSON-RPC request over HTTP POST and return the parsed response."""
        import requests as req_lib
        try:
            resp = req_lib.post(
                self.url,
                data=message,
                headers={**self.headers, "Content-Type": "application/json"},
                timeout=timeout,
            )
            if resp.status_code == 200:
                return resp.json()
            else:
                logger.warning(f"MCP HTTP server returned status {resp.status_code}: {resp.text[:200]}")
                return None
        except Exception as exc:
            logger.error(f"MCP HTTP request failed: {exc}")
            return None

    def stop(self) -> None:
        """No cleanup needed for HTTP transport."""
        pass

    @property
    def is_alive(self) -> bool:
        return True  # stateless


# ---------------------------------------------------------------------------
# MCPClient — the high-level client that wraps a transport
# ---------------------------------------------------------------------------

class MCPClient:
    """
    High-level MCP client. Manages the connection lifecycle, tool discovery,
    and tool invocation for a single MCP server.
    """

    PROTOCOL_VERSION = "2024-11-05"
    CLIENT_NAME = "jarvis-mcp-client"
    CLIENT_VERSION = "1.0.0"

    def __init__(self, name: str, transport):
        self.name = name
        self.transport = transport
        self.tools: List[MCPTool] = []
        self.server_info: Dict = {}
        self._initialized = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def connect(self) -> bool:
        """Start transport and perform the MCP initialize handshake."""
        try:
            self.transport.start()
        except Exception as exc:
            logger.error(f"[{self.name}] Transport start failed: {exc}")
            return False

        # Send initialize
        init_params = {
            "protocolVersion": self.PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": {
                "name": self.CLIENT_NAME,
                "version": self.CLIENT_VERSION,
            },
        }
        return self._do_handshake(init_params)

    def _do_handshake(self, init_params: Dict) -> bool:
        """Perform initialize + initialized notification."""
        req = _jsonrpc_request("initialize", init_params)

        if isinstance(self.transport, StdioTransport):
            self.transport.send(req)
            response = self.transport.receive(timeout=15)
        elif isinstance(self.transport, HttpTransport):
            response = self.transport.send_and_receive(req, timeout=15)
        else:
            logger.error(f"[{self.name}] Unknown transport type.")
            return False

        if response is None:
            logger.error(f"[{self.name}] No response to initialize handshake.")
            return False

        if "error" in response:
            logger.error(f"[{self.name}] Initialize error: {response['error']}")
            return False

        self.server_info = response.get("result", {})
        logger.info(
            f"[{self.name}] MCP server initialized: "
            f"{self.server_info.get('serverInfo', {}).get('name', 'unknown')}"
        )

        # Send initialized notification
        notif = _jsonrpc_notification("notifications/initialized")
        if isinstance(self.transport, StdioTransport):
            self.transport.send(notif)

        self._initialized = True
        return True

    def disconnect(self) -> None:
        """Cleanly shut down the transport."""
        self.transport.stop()
        self._initialized = False
        self.tools = []
        logger.info(f"[{self.name}] Disconnected.")

    # ------------------------------------------------------------------
    # Tool discovery
    # ------------------------------------------------------------------

    def discover_tools(self) -> List[MCPTool]:
        """Fetch the list of tools from the MCP server."""
        if not self._initialized:
            logger.warning(f"[{self.name}] Cannot discover tools — not initialized.")
            return []

        req = _jsonrpc_request("tools/list")

        if isinstance(self.transport, StdioTransport):
            self.transport.send(req)
            response = self.transport.receive(timeout=10)
        elif isinstance(self.transport, HttpTransport):
            response = self.transport.send_and_receive(req, timeout=10)
        else:
            return []

        if response is None or "error" in response:
            logger.warning(f"[{self.name}] tools/list failed: {response}")
            return []

        raw_tools = response.get("result", {}).get("tools", [])
        self.tools = []
        for t in raw_tools:
            tool = MCPTool(
                name=t.get("name", ""),
                description=t.get("description", ""),
                input_schema=t.get("inputSchema", {}),
                server_name=self.name,
            )
            self.tools.append(tool)
            logger.info(f"[{self.name}] Discovered tool: {tool.name}")

        return self.tools

    # ------------------------------------------------------------------
    # Tool invocation
    # ------------------------------------------------------------------

    def call_tool(self, tool_name: str, arguments: Dict) -> Dict:
        """
        Invoke a tool on the MCP server and return the result.

        Returns:
            dict with keys:
                - "content": list of content blocks (text, image, etc.)
                - "isError": bool
        """
        if not self._initialized:
            return {"content": [{"type": "text", "text": "MCP server not initialized."}], "isError": True}

        params = {"name": tool_name, "arguments": arguments}
        req = _jsonrpc_request("tools/call", params)

        if isinstance(self.transport, StdioTransport):
            self.transport.send(req)
            response = self.transport.receive(timeout=30)
        elif isinstance(self.transport, HttpTransport):
            response = self.transport.send_and_receive(req, timeout=30)
        else:
            return {"content": [{"type": "text", "text": "Unknown transport."}], "isError": True}

        if response is None:
            return {"content": [{"type": "text", "text": "MCP server did not respond."}], "isError": True}

        if "error" in response:
            err = response["error"]
            return {
                "content": [{"type": "text", "text": f"MCP error: {err.get('message', str(err))}"}],
                "isError": True,
            }

        result = response.get("result", {})
        return {
            "content": result.get("content", []),
            "isError": result.get("isError", False),
        }

    @property
    def is_connected(self) -> bool:
        return self._initialized and self.transport.is_alive
