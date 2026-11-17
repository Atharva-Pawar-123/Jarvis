"""
tests/v2/test_mcp_and_skills.py — MCP & Dynamic Skills Registry Tests
======================================================================
Validates DynamicSkillRegistry and CanonicalTool Integration:
  - Skill discovery from filesystem
  - Parameter schema mounting (manifest declared schemas)
  - Argument forwarding into skill handler (e.g. calculator expression)
  - Tool execution via StructuredToolRegistry
"""

import sys
import json
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import config
from modules.agent.tool_registry import StructuredToolRegistry
from modules.skills.registry import DynamicSkillRegistry


@pytest.fixture
def skill_registry():
    return DynamicSkillRegistry()


@pytest.fixture
def tool_registry():
    return StructuredToolRegistry()


class TestDynamicSkillDiscovery:
    def test_discover_and_mount_calculator(self, skill_registry, tool_registry):
        # Point to the actual skills directory
        skill_registry.discover_and_mount(tool_registry)

        # Calculator skill should be loaded
        loaded = skill_registry.list_loaded_skills()
        skill_names = [s["name"] for s in loaded]
        assert "calculator" in skill_names

        # Check canonical tool registration in tool_registry
        tool = tool_registry.get_tool("skill_calculator")
        assert tool is not None
        assert "[Skill]" in tool.description
        assert "expression" in tool.parameters_schema.get("properties", {})

    def test_execute_calculator_via_tool_registry(self, skill_registry, tool_registry):
        skill_registry.discover_and_mount(tool_registry)

        # Execute valid calculation via the canonical tool
        res = tool_registry.execute("skill_calculator", {"expression": "12 * 12 + 10"})
        assert res.success is True
        assert "154" in res.result

    def test_calculator_missing_param_handled(self, skill_registry, tool_registry):
        skill_registry.discover_and_mount(tool_registry)

        res = tool_registry.execute("skill_calculator", {})
        assert res.success is True
        assert "No expression provided" in res.result or "result" in res.result
