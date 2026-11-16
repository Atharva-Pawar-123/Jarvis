"""
modules/agent/tool_registry.py — Central Structured Tool Registry for JARVIS
===========================================================================
Defines Pydantic-validated tool schemas, execution timeouts, risk tiers,
and provides standardized JSON schemas for local LLM tool calling.
"""

import json
import logging
import inspect
from datetime import datetime
from typing import Dict, Any, Callable, Optional, List
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ToolDefinition(BaseModel):
    name: str
    description: str
    parameters_schema: Dict[str, Any]
    risk_level: str = "low"  # low, medium, high
    timeout_seconds: int = 15


class ToolExecutionResult(BaseModel):
    tool_name: str
    success: bool
    result: str
    error: Optional[str] = None
    execution_time_ms: int = 0


class StructuredToolRegistry:
    """Manages all tools available to JARVIS agents with Pydantic validation."""

    def __init__(self):
        self._tools: Dict[str, Dict[str, Any]] = {}

    def register(self, name: str, description: str, func: Callable, schema_cls: Optional[type[BaseModel]] = None, risk: str = "low", timeout: int = 15):
        """Register a tool with its execution function and optional Pydantic schema."""
        if schema_cls:
            schema = schema_cls.model_json_schema()
        else:
            # Fallback simple schema
            schema = {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "General input or query for this tool"}
                }
            }

        self._tools[name] = {
            "func": func,
            "description": description,
            "schema_cls": schema_cls,
            "schema": schema,
            "risk": risk,
            "timeout": timeout
        }

    def get_tool_definitions(self) -> List[ToolDefinition]:
        """Returns structured metadata for all registered tools."""
        return [
            ToolDefinition(
                name=k,
                description=v["description"],
                parameters_schema=v["schema"],
                risk_level=v["risk"],
                timeout_seconds=v["timeout"]
            )
            for k, v in self._tools.items()
        ]

    def get_system_prompt_prompt(self) -> str:
        """Generates a strict JSON schema prompt for local models."""
        tool_docs = []
        for name, data in self._tools.items():
            tool_docs.append({
                "name": name,
                "description": data["description"],
                "parameters": data["schema"].get("properties", {})
            })
        return json.dumps(tool_docs, indent=2)

    def execute(self, name: str, arguments: Dict[str, Any]) -> ToolExecutionResult:
        """Executes a tool with argument validation and error boundaries."""
        import time
        start_t = time.time()

        if name not in self._tools:
            return ToolExecutionResult(
                tool_name=name,
                success=False,
                result="",
                error=f"Tool '{name}' is not registered in JARVIS tools."
            )

        tool_meta = self._tools[name]
        func = tool_meta["func"]
        schema_cls = tool_meta.get("schema_cls")

        # Validate arguments using Pydantic if schema is provided
        clean_args = arguments
        if schema_cls and isinstance(arguments, dict):
            try:
                parsed = schema_cls(**arguments)
                clean_args = parsed.model_dump()
            except Exception as val_err:
                return ToolExecutionResult(
                    tool_name=name,
                    success=False,
                    result="",
                    error=f"Argument validation failed for {name}: {val_err}",
                    execution_time_ms=int((time.time() - start_t) * 1000)
                )

        # Call function
        try:
            sig = inspect.signature(func)
            if not sig.parameters:
                res = func()
            elif isinstance(clean_args, dict):
                # Check for direct kwargs match
                kwargs = {k: v for k, v in clean_args.items() if k in sig.parameters}
                has_kwargs = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values())
                if kwargs and not has_kwargs:
                    res = func(**kwargs)
                elif has_kwargs:
                    res = func(**clean_args)
                elif len(sig.parameters) == 1:
                    first_arg_name = list(sig.parameters.keys())[0]
                    first_val = next(iter(clean_args.values())) if clean_args else ""
                    res = func(first_val)
                else:
                    res = func()
            else:
                res = func(clean_args)

            elapsed = int((time.time() - start_t) * 1000)
            return ToolExecutionResult(
                tool_name=name,
                success=True,
                result=str(res),
                execution_time_ms=elapsed
            )

        except Exception as e:
            logger.error(f"Error executing tool {name}: {e}", exc_info=True)
            elapsed = int((time.time() - start_t) * 1000)
            return ToolExecutionResult(
                tool_name=name,
                success=False,
                result="",
                error=str(e),
                execution_time_ms=elapsed
            )
