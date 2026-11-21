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
from dataclasses import dataclass, field
from modules.agent.tool_registry import StructuredToolRegistry, ToolExecutionResult
from modules.security.permission_engine import PermissionEngine

logger = logging.getLogger(__name__)


@dataclass
class AgentStep:
    """Represents a single step in the agent reasoning loop."""
    thought: str = ""
    tool: Optional[str] = None
    tool_input: Dict[str, Any] = field(default_factory=dict)
    observation: Optional[str] = None
    is_final: bool = False
    final_answer: Optional[str] = None


class UnifiedAgentOrchestrator:
    """Central Brain for both Desktop and Voice interactions."""

    def __init__(self, llm, tools: StructuredToolRegistry, memory, permission_engine: PermissionEngine, four_tier_memory=None):
        self.llm = llm
        self.tools = tools
        self.memory = memory
        self.permission_engine = permission_engine
        self.four_tier_memory = four_tier_memory
        self.max_steps = 6

    async def execute_task(
        self,
        query: str,
        conversation_history: List[Dict[str, str]],
        step_callback: Optional[Callable[[str], Any]] = None,
        session_id: Optional[str] = None,
        cancellation_token: Optional[asyncio.Event] = None
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

        # Inject Working & Procedural Memory Context
        if self.four_tier_memory:
            try:
                working_ctx = self.four_tier_memory.format_working_context(active_session_id=session_id or "default", active_goal=query)
                if working_ctx:
                    messages.append({"role": "system", "content": f"Active Working Memory & Behavioral Habits:\n{working_ctx}"})
            except Exception as e:
                logger.warning(f"Failed to fetch 4-tier working context: {e}")

        # Inject brief memory context (Semantic)
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
            if cancellation_token and cancellation_token.is_set():
                logger.info("Orchestrator loop aborted: cancellation token set.")
                return "Task execution was cancelled."

            logger.info(f"Agent Loop iteration {step + 1}/{self.max_steps}")

            # Emit structured event: planning
            if step_callback:
                try:
                    event_payload = {
                        "type": "agent_event",
                        "event_type": "planning",
                        "step_number": step + 1,
                        "max_steps": self.max_steps,
                        "description": f"Analyzing task context and decomposing next action (step {step+1}/{self.max_steps})..."
                    }
                    cb_res = step_callback(event_payload)
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
                if step_callback:
                    try:
                        cb_res = step_callback({
                            "type": "agent_event",
                            "event_type": "final_deliverable",
                            "description": "Synthesized direct answer without tool calls."
                        })
                        if asyncio.iscoroutine(cb_res):
                            await cb_res
                    except Exception:
                        pass
                return response_clean

            thought = action_data.get("thought", "")
            action = action_data.get("action", "")
            action_input = action_data.get("action_input", {})
            final_answer = action_data.get("final_answer", "")

            if action == "FINAL_ANSWER" or final_answer:
                res_ans = final_answer or thought
                if step_callback:
                    try:
                        cb_res = step_callback({
                            "type": "agent_event",
                            "event_type": "final_deliverable",
                            "description": "Task plan fulfilled. Presenting final deliverable."
                        })
                        if asyncio.iscoroutine(cb_res):
                            await cb_res
                    except Exception:
                        pass

                # Automatically log completed episode into Episodic Memory
                if self.four_tier_memory:
                    try:
                        used_tools = [a.split(":")[0] for a in executed_actions]
                        self.four_tier_memory.log_episode(
                            user_goal=query,
                            outcome=res_ans,
                            tools_used=used_tools
                        )
                    except Exception as e:
                        logger.warning(f"Failed to log episode to 4-tier memory: {e}")
                return res_ans

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

            # Emit structured event: tool_selected
            if step_callback:
                try:
                    cb_res = step_callback({
                        "type": "agent_event",
                        "event_type": "tool_selected",
                        "tool": action,
                        "tool_input": action_input,
                        "thought": thought,
                        "description": f"Selected tool '{action}' based on reasoning: {thought[:80]}..." if thought else f"Selected tool '{action}'"
                    })
                    if asyncio.iscoroutine(cb_res):
                        await cb_res
                except Exception:
                    pass

            # Security Permission Gate with session context
            authorized, reason = await self.permission_engine.verify_and_authorize(
                action, action_input, session_id=session_id
            )
            if not authorized:
                observation = f"Permission Denied: {reason}"
                if step_callback:
                    try:
                        cb_res = step_callback({
                            "type": "agent_event",
                            "event_type": "approval_required",
                            "tool": action,
                            "description": f"Permission denied for '{action}': {reason}"
                        })
                        if asyncio.iscoroutine(cb_res):
                            await cb_res
                    except Exception:
                        pass
            else:
                if cancellation_token and cancellation_token.is_set():
                    logger.info("Orchestrator aborted prior to tool invocation: cancellation token set.")
                    return "Task execution was cancelled."

                if step_callback:
                    try:
                        cb_res = step_callback({
                            "type": "agent_event",
                            "event_type": "tool_executing",
                            "tool": action,
                            "tool_input": action_input,
                            "description": f"Executing tool '{action}' with parameters..."
                        })
                        if asyncio.iscoroutine(cb_res):
                            await cb_res
                    except Exception:
                        pass

                # Execute tool via registry
                exec_start = asyncio.get_event_loop().time()
                exec_res: ToolExecutionResult = await asyncio.to_thread(self.tools.execute, action, action_input)
                exec_duration_ms = int((asyncio.get_event_loop().time() - exec_start) * 1000)

                if exec_res.success:
                    observation = exec_res.result
                    if step_callback:
                        try:
                            cb_res = step_callback({
                                "type": "agent_event",
                                "event_type": "tool_completed",
                                "tool": action,
                                "duration_ms": exec_duration_ms,
                                "observation_snippet": str(observation)[:120],
                                "description": f"Tool '{action}' completed successfully in {exec_duration_ms}ms"
                            })
                            if asyncio.iscoroutine(cb_res):
                                await cb_res
                        except Exception:
                            pass
                else:
                    observation = f"Tool Execution Failed: {exec_res.error}"
                    if step_callback:
                        try:
                            cb_res = step_callback({
                                "type": "agent_event",
                                "event_type": "tool_completed",
                                "tool": action,
                                "duration_ms": exec_duration_ms,
                                "error": exec_res.error,
                                "description": f"Tool '{action}' failed: {exec_res.error}"
                            })
                            if asyncio.iscoroutine(cb_res):
                                await cb_res
                        except Exception:
                            pass

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
