"""
tests/v2/test_feature_parity.py — Feature Parity Verification Suite
===================================================================
Validates that all legacy tools and newly introduced modules are
correctly registered in the StructuredToolRegistry, possess valid
Pydantic or JSON schemas, enforce execution timeouts, and execute cleanly.
"""

import pytest
import time
from modules.agent.tool_registry import (
    StructuredToolRegistry,
    CanonicalTool,
    ToolExecutionResult,
    SendEmailInput,
    ReadEmailInput,
    SendWhatsAppInput,
    WebSearchInput,
    WeatherInput,
    NewsInput,
    SetReminderInput,
    ReadDocumentInput,
    SmartHomeControlInput,
    ExecuteCodeInput,
    BrowsePageInput,
)
from server.runtime import JarvisRuntime


@pytest.fixture
def runtime():
    """Instantiate a test runtime and register canonical tools."""
    rt = JarvisRuntime()
    rt._register_canonical_tools()
    return rt


def test_canonical_tools_registration(runtime):
    """Ensure all core and legacy parity tools are registered with schemas."""
    expected_tools = [
        "open_app",
        "close_app",
        "system_status",
        "take_screenshot",
        "describe_screen",
        "search_memory",
        "execute_code",
        "list_windows",
        "focus_window",
        "browse_page",
        "send_email",
        "read_email",
        "send_whatsapp",
        "web_search",
        "get_weather",
        "get_news",
        "set_reminder",
        "read_document",
        "smart_home_control",
    ]

    defs = runtime.tool_registry.get_tool_definitions()
    tool_names = [t.name for t in defs]

    for tool in expected_tools:
        assert tool in tool_names, f"Tool '{tool}' was not found in registered tools"
        meta = runtime.tool_registry.get_tool(tool)
        assert meta is not None
        assert meta.parameters_schema is not None
        assert "properties" in meta.parameters_schema or meta.parameters_schema == {}
        assert meta.risk_level in ["low", "medium", "high"]


def test_dual_schema_validation_pydantic():
    """Verify Pydantic input models reject malformed payloads."""
    reg = StructuredToolRegistry()
    reg.register(
        name="test_email",
        description="Test email sending",
        func=lambda to, subject, body: f"Sent to {to}",
        schema_cls=SendEmailInput
    )

    # Missing required fields
    res = reg.execute("test_email", {"to": "test@example.com"})
    assert not res.success
    assert "Argument validation failed" in res.error

    # Valid payload
    res = reg.execute("test_email", {"to": "test@example.com", "subject": "Hello", "body": "World"})
    assert res.success
    assert "Sent to test@example.com" in res.result


def test_dual_schema_validation_jsonschema():
    """Verify raw JSON Schema validation for skills and MCP dynamic tools."""
    reg = StructuredToolRegistry()
    custom_schema = {
        "type": "object",
        "properties": {
            "city": {"type": "string"},
            "days": {"type": "integer", "minimum": 1}
        },
        "required": ["city"]
    }
    reg.register(
        name="test_mcp_forecast",
        description="Forecast from MCP",
        func=lambda city, days=1: f"{city}: {days} days",
        custom_schema=custom_schema
    )

    # Missing required city
    res = reg.execute("test_mcp_forecast", {"days": 3})
    assert not res.success
    assert "Schema validation failed" in res.error

    # Valid payload
    res = reg.execute("test_mcp_forecast", {"city": "London", "days": 3})
    assert res.success
    assert "London: 3 days" in res.result


def test_tool_execution_timeout():
    """Verify that slow or hanging tools trigger timeout enforcement."""
    reg = StructuredToolRegistry()

    def slow_hanging_tool(duration: float = 2.0):
        time.sleep(duration)
        return "Finished"

    reg.register(
        name="slow_tool",
        description="Intentionally slow tool",
        func=slow_hanging_tool,
        timeout=1
    )

    # Should hit the 1s timeout and return clean failure
    res = reg.execute("slow_tool", {"duration": 3.0})
    assert not res.success
    assert "timed out after 1s" in res.error
