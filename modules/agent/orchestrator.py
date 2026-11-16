"""
modules/agent/orchestrator.py — Unified Agent Orchestrator for JARVIS
=====================================================================
The single source of truth for conversational and agentic reasoning.
Handles goal decomposition, tool execution loops with JSON validation,
duplicate-call prevention, budget tracking, and human-in-the-loop authorization.
"""

import json
import logging
import asyncio
import re
from typing import Dict, Any, List, Optional, Callable
from modules.agent.tool_registry import StructuredToolRegistry, ToolExecutionResult
from modules.security.permission_engine import PermissionEngine

logger = logging.getLogger(__name__)


class AgentStep(BaseModel := type("BaseModel", (), {})):
    thought: str = ""
    tool: Optional[str] = None
    tool_input: Dict[str, Any] = {}
    observation: Optional[str] = None
    is_final: bool = False
    final_answer: Optional[str] = None


class UnifiedAgentOrchestrator:
    """Central Brain for both Desktop and Voice interactions."""

    def __init__(self, llm, tools: StructuredToolRegistry, memory, permission_engine: PermissionEngine):
        self.llm = llm
        self.tools = tools
        self.memory = memory
        self.permission_engine = permission_engine
        self.max_steps = 6

    async def execute_task(
        self,
        query: str,
        conversation_history: List[Dict[str, str]],
        step_callback: Optional[Callable[[str], Any]] = None
    ) -> str:
        """
        Executes an autonomous goal-driven reasoning loop.
        step_callback: optional async or sync callback to stream intermediate reasoning steps to the UI.
        """
        tool_prompt = self.tools.get_system_prompt_prompt()

        system_instruction = (
            "You are JARVIS, an autonomous intelligence system. You accomplish tasks using your available tools.\n\n"
            f"AVAILABLE TOOLS SPECIFICATION (JSON Schema):\n{tool_prompt}\n\n"
            "INSTRUCTIONS:\n"
            "1. If you can answer directly without any tool, respond with a direct helpful answer.\n"
            "2. If you need a tool, emit a JSON block in this EXACT format:\n"
            "```json\n"
            "{\n"
            '  "thought": "Reasoning on what to do next",\n'
            '  "action": "tool_name",\n'
            '  "action_input": {"param_key": "param_value"}\n'
            "}\n"
            "```\n"
            "3. After an action is executed, you will observe the result and plan the next step.\n"
            "4. When finished, emit:\n"
            "```json\n"
            "{\n"
            '  "thought": "Task is complete.",\n'
            '  "action": "FINAL_ANSWER",\n'
            '  "final_answer": "Your complete, courteous response to sir."\n'
            "}\n"
            "```\n"
            "Always maintain the persona of JARVIS (polite, British accent, addressing the user as sir)."
        )

        messages = [{"role": "system", "content": system_instruction}]

        # Inject brief memory context
        try:
            mem_ctx = await asyncio.to_thread(self.memory.get_relevant_context, query)
            if mem_ctx:
                messages.append({"role": "system", "content": f"Relevant context from memory:\n{mem_ctx}"})
        except Exception:
            pass

        # Append recent conversational context
        for msg in conversation_history[-4:]:
            if msg.get("role") != "system":
                messages.append({"role": msg["role"], "content": msg["content"]})

        messages.append({"role": "user", "content": query})

        executed_actions: set[str] = set()

        for step in range(self.max_steps):
            logger.info(f"Agent Loop iteration {step + 1}/{self.max_steps}")

            # Notify UI
            if step_callback:
                try:
                    cb_res = step_callback(f"Thinking (step {step+1})...")
                    if asyncio.iscoroutine(cb_res):
                        await cb_res
                except Exception:
                    pass

            response = await asyncio.to_thread(self.llm.generate, messages, False)
            response_clean = response.strip()

            # Check if model returned a JSON action
            action_data = self._parse_json_action(response_clean)

            # If not tool action, treat as direct answer
            if not action_data:
                return response_clean

            thought = action_data.get("thought", "")
            action = action_data.get("action", "")
            action_input = action_data.get("action_input", {})
            final_answer = action_data.get("final_answer", "")

            if action == "FINAL_ANSWER" or final_answer:
                return final_answer or thought

            if not action:
                return response_clean

            # Prevent duplicate calls in the same loop
            action_key = f"{action}:{json.dumps(action_input, sort_keys=True)}"
            if action_key in executed_actions:
                messages.append({
                    "role": "user",
                    "content": f"Observation: Duplicate action '{action}' skipped. Please proceed to final answer."
                })
                continue
            executed_actions.add(action_key)

            # Security Permission Gate
            authorized, reason = await self.permission_engine.verify_and_authorize(action, action_input)
            if not authorized:
                observation = f"Permission Denied: {reason}"
            else:
                if step_callback:
                    try:
                        cb_res = step_callback(f"Executing tool: {action}...")
                        if asyncio.iscoroutine(cb_res):
                            await cb_res
                    except Exception:
                        pass

                # Execute tool via registry
                exec_res: ToolExecutionResult = await asyncio.to_thread(self.tools.execute, action, action_input)
                if exec_res.success:
                    observation = exec_res.result
                else:
                    observation = f"Tool Execution Failed: {exec_res.error}"

            # Append assistant message and observation
            messages.append({"role": "assistant", "content": response_clean})
            messages.append({"role": "user", "content": f"Observation for {action}:\n{observation}"})

        # Exceeded step budget
        return "I apologize, sir, but I reached my maximum planning steps before finalizing the task."

    def _parse_json_action(self, text: str) -> Optional[Dict[str, Any]]:
        """Safely parses structured action JSON from model output."""
        # Check for ```json ... ``` blocks
        json_match = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
        candidate = json_match.group(1) if json_match else text

        try:
            parsed = json.loads(candidate.strip())
            if isinstance(parsed, dict) and ("action" in parsed or "final_answer" in parsed):
                return parsed
        except Exception:
            pass

        # Try to find { ... } within string
        brace_match = re.search(r'\{.*\}', candidate, re.DOTALL)
        if brace_match:
            try:
                parsed = json.loads(brace_match.group(0))
                if isinstance(parsed, dict) and ("action" in parsed or "final_answer" in parsed):
                    return parsed
            except Exception:
                pass

        return None
