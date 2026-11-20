"""
modules/mcp/manager.py — MCP Plugin Manager
===========================================
Reads mcp.json configuration, initializes MCPClient instances,
and manages the lifecycle of all connected MCP servers.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional

import config
from modules.mcp.client import MCPClient, MCPTool, StdioTransport, HttpTransport
from modules.mcp.permissions import MCPPermissions

logger = logging.getLogger(__name__)

# Default config if mcp.json doesn't exist
DEFAULT_MCP_CONFIG = {
    "mcpServers": {
        # Example: sqlite database integration
        # "sqlite": {
        #     "command": "uvx",
        #     "args": ["mcp-server-sqlite", "--db-path", "jarvis_data.sqlite"]
        # }
    }
}


class PluginManager:
    """
    Manages the ecosystem of MCP servers.
    """

    def __init__(self, config_path: str = "mcp.json", permissions: Optional[MCPPermissions] = None):
        # We store mcp.json at the root of JARVIS
        self.config_path = Path(config.BASE_DIR) / config_path
        self.permissions = permissions or MCPPermissions()
        
        self.clients: Dict[str, MCPClient] = {}
        self._all_tools: List[MCPTool] = []

    def start_all(self) -> None:
        """Read config and start all enabled servers."""
        logger.info("Initializing MCP Plugin Manager...")
        self._ensure_config()
        
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
        except Exception as exc:
            logger.error(f"Failed to load MCP config {self.config_path}: {exc}")
            return

        servers = cfg.get("mcpServers", {})
        
        for name, params in servers.items():
            self._start_server(name, params)
            
        self._aggregate_tools()
        logger.info(f"MCP Manager started. Total tools available: {len(self._all_tools)}")

    def _ensure_config(self) -> None:
        """Create a default mcp.json if it doesn't exist."""
        if not self.config_path.exists():
            logger.info(f"Creating default MCP config at {self.config_path}")
            try:
                with open(self.config_path, "w", encoding="utf-8") as f:
                    json.dump(DEFAULT_MCP_CONFIG, f, indent=4)
            except Exception as exc:
                logger.error(f"Failed to create default mcp.json: {exc}")

    def _start_server(self, name: str, params: Dict) -> None:
        """Initialize and connect to a single MCP server based on its config."""
        logger.info(f"Starting MCP Server: {name}...")
        
        transport = None
        
        # Determine transport type
        if "command" in params:
            # Stdio transport — verify the command binary exists first
            cmd = params["command"]
            import shutil
            if not shutil.which(cmd):
                logger.info(
                    f"MCP Server '{name}' skipped: command '{cmd}' not found on PATH. "
                    f"Install it to enable this plugin."
                )
                return
            args = params.get("args", [])
            env = params.get("env", None)
            transport = StdioTransport(command=cmd, args=args, env=env)
        elif "url" in params:
            # HTTP transport
            url = params["url"]
            headers = params.get("headers", None)
            transport = HttpTransport(url=url, headers=headers)
        else:
            logger.warning(f"Invalid config for MCP server '{name}': Must specify 'command' or 'url'.")
            return

        try:
            client = MCPClient(name=name, transport=transport)
            if client.connect():
                # Discover tools immediately upon connection
                tools = client.discover_tools()
                self.clients[name] = client
                logger.info(f"MCP Server '{name}' connected successfully. Exposes {len(tools)} tools.")
            else:
                logger.warning(f"MCP Server '{name}' could not be connected. It will be skipped.")
        except Exception as exc:
            logger.warning(f"MCP Server '{name}' startup failed: {exc}. Skipping.")

    def _aggregate_tools(self) -> None:
        """Update the flattened list of all available tools across all servers."""
        self._all_tools = []
        for client in self.clients.values():
            if client.is_connected:
                self._all_tools.extend(client.tools)

    def get_all_tools_schema(self) -> List[Dict]:
        """Get the LLM-compatible tool schema for every connected tool."""
        return [t.to_llm_schema() for t in self._all_tools]

    def call_tool(self, server_name: str, tool_name: str, arguments: Dict) -> Dict:
        """
        Execute an MCP tool, subject to permissions checking.
        """
        if server_name not in self.clients:
            return {"error": f"MCP server '{server_name}' is not connected."}

        client = self.clients[server_name]
        
        # Check permissions
        # Try to find the description
        description = ""
        for t in client.tools:
            if t.name == tool_name:
                description = t.description
                break
                
        if not self.permissions.is_allowed(tool_name, server_name, description):
            return {"error": f"Permission denied by user for {server_name}/{tool_name}."}

        # Call the tool
        try:
            logger.info(f"Calling MCP Tool: {server_name}/{tool_name} with args: {arguments}")
            result = client.call_tool(tool_name, arguments)
            return result
        except Exception as exc:
            logger.error(f"Error calling MCP Tool {server_name}/{tool_name}: {exc}")
            return {"error": str(exc)}

    def stop_all(self) -> None:
        """Cleanly disconnect all servers."""
        for name, client in self.clients.items():
            logger.info(f"Stopping MCP Server: {name}")
            try:
                client.disconnect()
            except Exception as exc:
                logger.error(f"Error disconnecting MCP Server '{name}': {exc}")
        self.clients.clear()
        self._all_tools.clear()
