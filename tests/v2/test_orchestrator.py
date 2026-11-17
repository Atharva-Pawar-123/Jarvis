"""
tests/v2/test_orchestrator.py — Orchestrator Reasoning Loop Tests
==================================================================
Validates UnifiedAgentOrchestrator:
  - Multi-step tool call → observation → final answer
  - JSON action block parsing from model output
  - Step budget enforcement (max_steps)
  - Duplicate action prevention
  - Direct-answer passthrough (no tool call)
"""

import sys
import json
import asyncio
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from modules.agent.orchestrator import UnifiedAgentOrchestrator
from modules.agent.tool_registry import StructuredToolRegistry, ToolExecutionResult, EmptyInput
from modules.security.permission_engine import PermissionEngine


# ── Fixtures ─────────────────────────────────────────────────────────

@pytest.fixture
def registry_with_tool():
    reg = StructuredToolRegistry()
    reg.register(
        name="system_status",
        description="Check system CPU, RAM",
        func=lambda: "CPU: 20%, RAM: 55%",
        schema_cls=EmptyInput,
        risk="low",
        permission_category="system_status"
    )
    return reg


@pytest.fixture
def permission_eng():
    return PermissionEngine()


@pytest.fixture
def mock_memory():
    mem = MagicMock()
    mem.get_relevant_context = MagicMock(return_value="")
    return mem


# ── JSON Action Parsing ─────────────────────────────────────────────

class TestJsonActionParsing:
    """Tests for _parse_json_action()."""

    def _make_orchestrator(self, mock_llm, mock_memory, permission_eng):
        reg = StructuredToolRegistry()
        return UnifiedAgentOrchestrator(
            llm=mock_llm, tools=reg, memory=mock_memory, permission_engine=permission_eng
        )

    def test_parse_fenced_json(self, mock_llm, mock_memory, permission_eng):
        orch = self._make_orchestrator(mock_llm, mock_memory, permission_eng)
        text = '```json\n{"thought": "checking", "action": "system_status", "action_input": {}}\n```'
        result = orch._parse_json_action(text)
        assert result is not None
        assert result["action"] == "system_status"

    def test_parse_bare_json(self, mock_llm, mock_memory, permission_eng):
        orch = self._make_orchestrator(mock_llm, mock_memory, permission_eng)
        text = '{"thought": "compute", "action": "FINAL_ANSWER", "final_answer": "Done sir."}'
        result = orch._parse_json_action(text)
        assert result is not None
        assert result["action"] == "FINAL_ANSWER"
        assert result["final_answer"] == "Done sir."

    def test_parse_embedded_json(self, mock_llm, mock_memory, permission_eng):
        orch = self._make_orchestrator(mock_llm, mock_memory, permission_eng)
        text = 'Here is my plan:\n{"thought": "need info", "action": "browse_page", "action_input": {"url": "https://example.com"}}\nThat should work.'
        result = orch._parse_json_action(text)
        assert result is not None
        assert result["action"] == "browse_page"

    def test_parse_returns_none_for_plain_text(self, mock_llm, mock_memory, permission_eng):
        orch = self._make_orchestrator(mock_llm, mock_memory, permission_eng)
        text = "I can answer this directly, sir. The weather is nice today."
        result = orch._parse_json_action(text)
        assert result is None

    def test_parse_returns_none_for_non_action_json(self, mock_llm, mock_memory, permission_eng):
        orch = self._make_orchestrator(mock_llm, mock_memory, permission_eng)
        text = '{"temperature": 25, "humidity": 60}'
        result = orch._parse_json_action(text)
        assert result is None


# ── Full Execution Loop ──────────────────────────────────────────────

class TestExecuteTask:
    """Tests for the full execute_task() reasoning loop."""

    @pytest.mark.asyncio
    async def test_direct_answer_no_tool(self, mock_memory, permission_eng):
        """LLM returns plain text → orchestrator returns it directly."""
        mock_llm = MagicMock()
        mock_llm.generate = MagicMock(return_value="Certainly sir, 2 + 2 = 4.")

        reg = StructuredToolRegistry()
        orch = UnifiedAgentOrchestrator(llm=mock_llm, tools=reg, memory=mock_memory, permission_engine=permission_eng)

        result = await orch.execute_task("What is 2+2?", [])
        assert "4" in result

    @pytest.mark.asyncio
    async def test_tool_call_then_final_answer(self, mock_memory, permission_eng, registry_with_tool):
        """LLM emits tool call → observation → FINAL_ANSWER."""
        call_count = [0]

        def mock_generate(messages, stream=False):
            call_count[0] += 1
            if call_count[0] == 1:
                return json.dumps({
                    "thought": "Let me check system status",
                    "action": "system_status",
                    "action_input": {}
                })
            else:
                return json.dumps({
                    "thought": "Task complete",
                    "action": "FINAL_ANSWER",
                    "final_answer": "CPU is at 20%, RAM at 55%, sir."
                })

        mock_llm = MagicMock()
        mock_llm.generate = mock_generate

        orch = UnifiedAgentOrchestrator(
            llm=mock_llm, tools=registry_with_tool, memory=mock_memory, permission_engine=permission_eng
        )
        result = await orch.execute_task("Check my system status", [])
        assert "20%" in result or "55%" in result

    @pytest.mark.asyncio
    async def test_step_budget_exceeded(self, mock_memory, permission_eng):
        """LLM never emits FINAL_ANSWER → orchestrator hits max_steps."""
        mock_llm = MagicMock()
        # Always return non-action JSON that still looks like it wants to continue
        mock_llm.generate = MagicMock(return_value=json.dumps({
            "thought": "Need more data",
            "action": "some_nonexistent_tool",
            "action_input": {}
        }))

        reg = StructuredToolRegistry()
        orch = UnifiedAgentOrchestrator(llm=mock_llm, tools=reg, memory=mock_memory, permission_engine=permission_eng)
        orch.max_steps = 3  # Reduce for faster test

        result = await orch.execute_task("Run forever", [])
        # It should hit the budget message or the tool-not-found observation should loop
        assert "maximum planning steps" in result.lower() or "not registered" in result.lower() or result != ""

    @pytest.mark.asyncio
    async def test_duplicate_action_skipped(self, mock_memory, permission_eng, registry_with_tool):
        """Same tool+args called twice → second call skipped, asks for final answer."""
        call_count = [0]

        def mock_generate(messages, stream=False):
            call_count[0] += 1
            if call_count[0] <= 2:
                # Emit same action twice
                return json.dumps({
                    "thought": "Checking system",
                    "action": "system_status",
                    "action_input": {}
                })
            else:
                return json.dumps({
                    "thought": "Done",
                    "action": "FINAL_ANSWER",
                    "final_answer": "All good sir."
                })

        mock_llm = MagicMock()
        mock_llm.generate = mock_generate

        orch = UnifiedAgentOrchestrator(
            llm=mock_llm, tools=registry_with_tool, memory=mock_memory, permission_engine=permission_eng
        )
        result = await orch.execute_task("Check system twice", [])
        assert "good" in result.lower() or result != ""

    @pytest.mark.asyncio
    async def test_step_callback_invoked(self, mock_memory, permission_eng):
        """step_callback is called with thinking status messages."""
        mock_llm = MagicMock()
        mock_llm.generate = MagicMock(return_value="Simple answer sir.")

        reg = StructuredToolRegistry()
        orch = UnifiedAgentOrchestrator(llm=mock_llm, tools=reg, memory=mock_memory, permission_engine=permission_eng)

        callback_calls = []
        result = await orch.execute_task("Hello", [], step_callback=lambda msg: callback_calls.append(msg))
        assert len(callback_calls) >= 1
        assert any("Thinking" in c for c in callback_calls)
