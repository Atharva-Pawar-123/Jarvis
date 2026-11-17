"""
modules/agent/__init__.py
"""
from .tool_registry import StructuredToolRegistry, CanonicalTool, ToolExecutionResult
from .orchestrator import UnifiedAgentOrchestrator

# Backward compatibility alias
ToolDefinition = CanonicalTool

__all__ = ["StructuredToolRegistry", "CanonicalTool", "ToolDefinition", "ToolExecutionResult", "UnifiedAgentOrchestrator"]
