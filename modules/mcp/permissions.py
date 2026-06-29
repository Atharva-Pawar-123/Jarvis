"""
modules/mcp/permissions.py — MCP Security & Permissions
=======================================================
Controls which MCP tools are allowed to execute and which require
explicit user approval. High-risk operations (file deletion, shell
execution, database mutations) are flagged and require verbal
confirmation before JARVIS proceeds.
"""

import logging
from typing import Callable, Optional, Set

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Risk classification
# ---------------------------------------------------------------------------

# Keywords in tool names/descriptions that suggest high-risk operations
HIGH_RISK_KEYWORDS = frozenset([
    "delete", "drop", "remove", "execute", "shell", "run",
    "write", "modify", "update", "insert", "create", "send",
    "deploy", "push", "publish", "admin", "sudo", "kill",
])

# Tools that are always safe to call without prompting
ALWAYS_ALLOW = frozenset([
    "read", "get", "list", "search", "fetch", "query", "describe",
    "count", "info", "status", "version", "ping", "health",
])


class MCPPermissions:
    """
    Manages tool-level permissions for MCP servers.

    Modes:
        - "ask": Prompt the user verbally before executing high-risk tools (default).
        - "allow_all": Auto-approve everything (for trusted/local servers).
        - "deny_all": Block all MCP tool calls (safety lockdown).
    """

    def __init__(
        self,
        mode: str = "ask",
        tts_callback: Optional[Callable] = None,
        stt_callback: Optional[Callable] = None,
    ):
        self.mode = mode
        self.tts_callback = tts_callback
        self.stt_callback = stt_callback
        self._approved_tools: Set[str] = set()
        self._denied_tools: Set[str] = set()

    def is_allowed(self, tool_name: str, server_name: str, description: str = "") -> bool:
        """
        Check if a tool call should be allowed.

        Returns True if allowed, False if denied.
        For "ask" mode, will verbally prompt the user and wait for a response.
        """
        full_name = f"{server_name}/{tool_name}"

        # Check explicit overrides first
        if full_name in self._approved_tools:
            return True
        if full_name in self._denied_tools:
            logger.info(f"Tool {full_name} is explicitly denied.")
            return False

        if self.mode == "allow_all":
            return True

        if self.mode == "deny_all":
            logger.info(f"Tool {full_name} denied (deny_all mode).")
            return False

        # "ask" mode: classify risk
        risk = self._classify_risk(tool_name, description)

        if risk == "low":
            return True

        # High risk — ask user
        return self._ask_user(full_name, description)

    def _classify_risk(self, tool_name: str, description: str) -> str:
        """Classify a tool as 'low' or 'high' risk based on its name and description."""
        combined = (tool_name + " " + description).lower()

        # Check if it matches any always-allow pattern
        for safe_word in ALWAYS_ALLOW:
            if combined.startswith(safe_word) or tool_name.lower().startswith(safe_word):
                return "low"

        # Check for high-risk keywords
        for risky_word in HIGH_RISK_KEYWORDS:
            if risky_word in combined:
                return "high"

        # Default to low risk for unknown tools
        return "low"

    def _ask_user(self, full_name: str, description: str) -> bool:
        """
        Verbally ask the user for permission to execute a potentially dangerous tool.

        Returns True if user approves, False otherwise.
        """
        prompt_msg = (
            f"Sir, the MCP tool '{full_name}' wants to perform a potentially sensitive operation. "
            f"Description: {description}. Shall I proceed?"
        )

        logger.info(f"Requesting user approval for tool: {full_name}")

        if self.tts_callback:
            self.tts_callback(prompt_msg)

        # Try to get verbal confirmation
        if self.stt_callback:
            try:
                response = self.stt_callback(timeout=10)
                if response:
                    response_lower = response.lower().strip()
                    if any(word in response_lower for word in ["yes", "go ahead", "proceed", "approve", "do it", "allow"]):
                        logger.info(f"User approved tool: {full_name}")
                        self._approved_tools.add(full_name)
                        return True
                    elif any(word in response_lower for word in ["no", "deny", "cancel", "stop", "don't"]):
                        logger.info(f"User denied tool: {full_name}")
                        self._denied_tools.add(full_name)
                        return False
            except Exception as exc:
                logger.warning(f"Failed to get user confirmation: {exc}")

        # If we can't ask, default to deny for safety
        logger.warning(f"Could not confirm user intent. Denying tool: {full_name}")
        return False

    def approve_tool(self, server_name: str, tool_name: str) -> None:
        """Explicitly approve a tool for future calls."""
        full_name = f"{server_name}/{tool_name}"
        self._approved_tools.add(full_name)
        self._denied_tools.discard(full_name)
        logger.info(f"Tool explicitly approved: {full_name}")

    def deny_tool(self, server_name: str, tool_name: str) -> None:
        """Explicitly deny a tool for future calls."""
        full_name = f"{server_name}/{tool_name}"
        self._denied_tools.add(full_name)
        self._approved_tools.discard(full_name)
        logger.info(f"Tool explicitly denied: {full_name}")

    def reset(self) -> None:
        """Clear all approval/denial caches."""
        self._approved_tools.clear()
        self._denied_tools.clear()
