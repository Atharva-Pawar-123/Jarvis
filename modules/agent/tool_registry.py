"""
modules/agent/tool_registry.py — Canonical Structured Tool Registry for JARVIS
==============================================================================
Defines the CanonicalTool contract, strict parameter schemas, execution timeouts,
risk tiers, and generates standardized JSON schemas for local LLM tool calling.
"""

import json
import logging
import inspect
import time
from datetime import datetime
from typing import Dict, Any, Callable, Optional, List, Union
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class CanonicalTool(BaseModel):
    """Immutable contract defining a canonical tool in JARVIS."""
    name: str
    description: str
    parameters_schema: Dict[str, Any]
    risk_level: str = "low"  # low, medium, high
    permission_category: str = "custom"
    timeout_seconds: int = 15

    model_config = {"arbitrary_types_allowed": True}


class ToolExecutionResult(BaseModel):
    """Standardized result returned after executing any tool."""
    tool_name: str
    success: bool
    result: str
    error: Optional[str] = None
    execution_time_ms: int = 0


# Built-in tool input models for type safety
class CalculatorInput(BaseModel):
    expression: str = Field(..., description="Math expression to evaluate, e.g. '12 * 45 + 7'")

class OpenAppInput(BaseModel):
    app_name: str = Field(..., description="Name of the application to open, e.g. 'notepad', 'chrome'")

class CloseAppInput(BaseModel):
    app_name: str = Field(..., description="Name of the application to close")

class FocusWindowInput(BaseModel):
    window_name: str = Field(..., description="Title or keyword of window to focus")

class BrowsePageInput(BaseModel):
    url: str = Field(..., description="HTTP or HTTPS URL to fetch content from")

class ExecuteCodeInput(BaseModel):
    code: str = Field(..., description="Python code block to execute in sandbox")

class SearchMemoryInput(BaseModel):
    query: str = Field(..., description="Search phrase or keyword for long-term memory")

class SendEmailInput(BaseModel):
    to: str = Field(..., description="Recipient email address")
    subject: str = Field(..., description="Subject line of the email")
    body: str = Field(..., description="Body text content of the email")

class ReadEmailInput(BaseModel):
    count: int = Field(5, description="Number of recent emails to read from inbox")

class SendWhatsAppInput(BaseModel):
    phone_number: str = Field(..., description="Phone number with country code, e.g. +1234567890")
    message: str = Field(..., description="Message text to send")

class WebSearchInput(BaseModel):
    query: str = Field(..., description="Search query keyword or question")

class WeatherInput(BaseModel):
    location: str = Field("", description="City or location name, e.g. 'London', 'New York' (leave empty for auto/current)")

class NewsInput(BaseModel):
    count: int = Field(5, description="Number of top headlines to fetch")

class SetReminderInput(BaseModel):
    time_str: str = Field(..., description="Time expression for reminder, e.g. 'in 10 minutes', 'at 5 PM'")
    task: str = Field(..., description="What to remind the user about")

class ReadDocumentInput(BaseModel):
    file_path: str = Field(..., description="Absolute or relative path to PDF, DOCX, or text file")

class SmartHomeControlInput(BaseModel):
    device: str = Field(..., description="Name or identifier of the smart home device")
    action: str = Field(..., description="Action to perform, e.g. 'turn_on', 'turn_off', 'toggle'")

class DeepResearchInput(BaseModel):
    topic: str = Field(..., description="Subject or question for comprehensive multi-query research and synthesis")
    max_subqueries: int = Field(3, description="Number of subqueries to investigate (default: 3)")

class CodeProposalInput(BaseModel):
    target_file: str = Field(..., description="Relative path of file to inspect, modify or repair")
    task_instruction: str = Field(..., description="Instruction describing required code modifications or fixes")

class IngestDocumentInput(BaseModel):
    file_path: str = Field(..., description="Path to PDF, DOCX, or text file to ingest into Semantic RAG")

class EmptyInput(BaseModel):
    pass


class StructuredToolRegistry:
    """Manages all canonical tools available to JARVIS agents with Pydantic validation."""

    def __init__(self):
        self._tools: Dict[str, Dict[str, Any]] = {}

    def register(
        self,
        name: str,
        description: str,
        func: Callable,
        schema_cls: Optional[type[BaseModel]] = None,
        custom_schema: Optional[Dict[str, Any]] = None,
        risk: str = "low",
        permission_category: Optional[str] = None,
        timeout: int = 15
    ):
        """Register a tool with its execution callable and exact parameter schema."""
        if schema_cls:
            schema = schema_cls.model_json_schema()
        elif custom_schema:
            schema = custom_schema
        else:
            schema = {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "General input parameter for this tool"}
                }
            }

        category = permission_category or name

        self._tools[name] = {
            "name": name,
            "func": func,
            "description": description,
            "schema_cls": schema_cls,
            "schema": schema,
            "risk": risk.lower(),
            "permission_category": category,
            "timeout": timeout
        }

    def get_tool(self, name: str) -> Optional[CanonicalTool]:
        """Returns CanonicalTool metadata for a single tool."""
        data = self._tools.get(name)
        if not data:
            return None
        return CanonicalTool(
            name=data["name"],
            description=data["description"],
            parameters_schema=data["schema"],
            risk_level=data["risk"],
            permission_category=data["permission_category"],
            timeout_seconds=data["timeout"]
        )

    def get_tool_definitions(self) -> List[CanonicalTool]:
        """Returns structured metadata for all registered canonical tools."""
        return [
            CanonicalTool(
                name=k,
                description=v["description"],
                parameters_schema=v["schema"],
                risk_level=v["risk"],
                permission_category=v["permission_category"],
                timeout_seconds=v["timeout"]
            )
            for k, v in self._tools.items()
        ]

    def get_registered_capabilities(self) -> List[str]:
        """Returns high-level user-facing capabilities based strictly on registered online tools."""
        caps = []
        for name, data in self._tools.items():
            desc = data["description"].split(".")[0]
            caps.append(f"- {name}: {desc}")
        return caps

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
        """Executes a tool with strict argument unpacking, validation, and error boundaries."""
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

        # Validate arguments using Pydantic or JSON Schema
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
        elif tool_meta.get("schema") and isinstance(arguments, dict):
            # Validate raw JSON schema (for dynamic skills and MCP tools)
            try:
                import jsonschema
                jsonschema.validate(instance=arguments, schema=tool_meta["schema"])
            except Exception as json_err:
                return ToolExecutionResult(
                    tool_name=name,
                    success=False,
                    result="",
                    error=f"Schema validation failed for {name}: {json_err.message if hasattr(json_err, 'message') else json_err}",
                    execution_time_ms=int((time.time() - start_t) * 1000)
                )

        # Call function with execution timeout enforcement
        timeout = tool_meta.get("timeout", 15)
        try:
            import concurrent.futures

            sig = inspect.signature(func)
            def _invoke():
                if not sig.parameters:
                    return func()
                elif isinstance(clean_args, dict):
                    kwargs = {k: v for k, v in clean_args.items() if k in sig.parameters}
                    has_kwargs = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values())
                    if kwargs and not has_kwargs:
                        return func(**kwargs)
                    elif has_kwargs:
                        return func(**clean_args)
                    elif len(sig.parameters) == 1:
                        first_val = next(iter(clean_args.values())) if clean_args else ""
                        return func(first_val)
                    else:
                        return func()
                else:
                    return func(clean_args)

            # Use non-waiting executor to avoid blocking on hung worker threads
            executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
            try:
                future = executor.submit(_invoke)
                res = future.result(timeout=timeout)
            finally:
                # Do not wait for stalled worker thread to prevent freezing the orchestrator
                executor.shutdown(wait=False, cancel_futures=True)

            elapsed = int((time.time() - start_t) * 1000)

            # Contract verification: False, None, or dict with explicit truthy error indicates failure.
            # Notice: If res is a dict, an empty or None 'error' (e.g. {"error": ""}) is NOT a failure.
            is_failure = False
            err_msg = None
            if res is False:
                is_failure = True
                err_msg = "Tool returned False."
            elif isinstance(res, dict):
                # If explicit 'success' field is present, it is authoritative
                if "success" in res and res["success"] is False:
                    is_failure = True
                    err_msg = res.get("error") or "Tool reported success=False"
                elif res.get("error"):
                    # Only treat as failure if error is truthy (non-empty string or error object)
                    is_failure = True
                    err_msg = res.get("error")

            if is_failure:
                return ToolExecutionResult(
                    tool_name=name,
                    success=False,
                    result=str(res) if res is not False else "",
                    error=str(err_msg),
                    execution_time_ms=elapsed
                )

            return ToolExecutionResult(
                tool_name=name,
                success=True,
                result=str(res),
                execution_time_ms=elapsed
            )

        except concurrent.futures.TimeoutError:
            elapsed = int((time.time() - start_t) * 1000)
            logger.warning(f"Tool {name} execution timed out after {timeout} seconds.")
            return ToolExecutionResult(
                tool_name=name,
                success=False,
                result="",
                error=f"Execution timed out after {timeout}s",
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
