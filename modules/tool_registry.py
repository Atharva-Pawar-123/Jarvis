"""
modules/tool_registry.py — JARVIS Tool Registry & Guardrails
=============================================================
Central registry for all tools JARVIS can use. Implements strict permissions,
input schemas, and Human-in-the-Loop (HITL) checks for destructive actions.
"""

import logging
from typing import Dict, Any, Callable, Optional

logger = logging.getLogger(__name__)

class Tool:
    """Represents an executable tool that JARVIS can use."""
    def __init__(
        self, 
        name: str, 
        description: str, 
        is_destructive: bool, 
        handler: Callable,
        input_schema: Optional[Dict] = None
    ):
        self.name = name
        self.description = description
        self.is_destructive = is_destructive
        self.handler = handler
        self.input_schema = input_schema or {}
        # If destructive, it strictly requires human approval
        self.requires_human_approval = is_destructive

    def execute(self, approval_callback: Optional[Callable] = None, *args, **kwargs) -> Any:
        if self.requires_human_approval:
            logger.warning(f"Tool '{self.name}' requires HITL approval.")
            if approval_callback:
                approved = approval_callback(self.name, args, kwargs)
                if not approved:
                    logger.warning(f"Execution of '{self.name}' denied by user.")
                    return "Action cancelled by user."
            else:
                logger.error(f"No approval callback provided for destructive tool '{self.name}'. Auto-denying.")
                return "Action failed: Missing human approval mechanism."
                
        return self.handler(*args, **kwargs)


class ToolRegistry:
    """Central registry managing all JARVIS tools."""
    def __init__(self):
        self.tools: Dict[str, Tool] = {}

    def register(self, tool: Tool):
        self.tools[tool.name] = tool
        logger.info(f"Registered tool: {tool.name} (Destructive: {tool.is_destructive})")

    def get_tool(self, name: str) -> Optional[Tool]:
        return self.tools.get(name)

    def execute_tool(self, name: str, approval_callback: Optional[Callable] = None, *args, **kwargs):
        tool = self.get_tool(name)
        if not tool:
            raise ValueError(f"Tool '{name}' not found in registry.")
        return tool.execute(approval_callback, *args, **kwargs)

    def get_all_tool_descriptions(self) -> str:
        """Returns a formatted string of all tools, used to inject into LLM prompts."""
        desc = ""
        for name, tool in self.tools.items():
            desc += f"- {name}: {tool.description} (Requires Approval: {tool.requires_human_approval})\n"
        return desc
