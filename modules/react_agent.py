import json
import logging
import re

class ReActAgent:
    """
    Reason + Act Agent for JARVIS.
    Allows JARVIS to autonomously chain multiple tools to accomplish a complex goal.
    """
    
    def __init__(self, llm, tools: dict, memory):
        self.llm = llm
        self.tools = tools
        self.max_steps = 8
        self.memory = memory
        logging.info("ReAct Agent initialized.")

    def get_tool_descriptions(self) -> str:
        # Assuming tools is a dict like: {"tool_name": {"func": callable, "desc": "description"}}
        lines = ["AVAILABLE TOOLS:"]
        for name, data in self.tools.items():
            desc = data.get("desc", "No description")
            lines.append(f"- {name}: {desc}")
        return "\n".join(lines)

    def run(self, user_query: str, conversation_history: list) -> str:
        """Executes the ReAct loop."""
        
        # Build System Prompt
        react_prompt = (
            "You are JARVIS executing a complex request. You have access to tools.\n"
            "For each step, decide: do you need a tool, or can you answer directly?\n\n"
            "FORMAT each step exactly like this (do not use brackets):\n"
            "Thought: your reasoning about what to do next\n"
            "Action: tool_name or FINAL_ANSWER\n"
            "Action Input: JSON parameters for the tool (e.g. {\"query\": \"search term\"}) or your final response\n\n"
            f"{self.get_tool_descriptions()}\n\n"
            "Stop when you have enough information to give a final answer.\n"
            "Use FINAL_ANSWER as the Action when done."
        )
        
        # Initial context injection
        messages = [{"role": "system", "content": react_prompt}]
        
        # Add a snippet of recent history just for context
        for msg in conversation_history[-4:]:
            if msg["role"] != "system":
                messages.append(msg)
                
        messages.append({"role": "user", "content": user_query})
        
        for step in range(self.max_steps):
            logging.info(f"ReAct Loop Step {step+1}/{self.max_steps}")
            
            # 1. REASON
            response = self.llm._generate_blocking(messages, self.llm.PRIMARY_MODEL)
            messages.append({"role": "assistant", "content": response})
            
            # 2. PARSE
            action = self._extract(response, "Action:")
            action_input = self._extract(response, "Action Input:")
            if action:
                action = action.strip("[]'\" \t")
            
            if not action:
                # If LLM broke format, gently push it back
                messages.append({"role": "user", "content": "Format error. Remember to use 'Action:' and 'Action Input:'. Continue."})
                continue
                
            if action == "FINAL_ANSWER":
                return action_input
                
            if action not in self.tools:
                messages.append({"role": "user", "content": f"Observation: Tool '{action}' not found. Available tools: {list(self.tools.keys())}"})
                continue
                
            # 3. OBSERVE (Execute Tool)
            try:
                # Try to parse Action Input as JSON
                try:
                    params = json.loads(action_input)
                except (json.JSONDecodeError, TypeError):
                    # If it's not valid JSON, treat as a string param
                    params = {"text": action_input} if action_input else {}
                    
                tool_func = self.tools[action]["func"]
                if isinstance(params, dict):
                    try:
                        result = tool_func(**params)
                    except TypeError:
                        if not params or not any(params.values()):
                            result = tool_func()
                        else:
                            first_val = next(iter(params.values()))
                            result = tool_func(first_val)
                else:
                    try:
                        result = tool_func(params)
                    except TypeError:
                        result = tool_func()
                    
                observation = f"Observation: {result}"
                
            except Exception as e:
                observation = f"Observation: Tool execution failed with error: {str(e)}"
                
            messages.append({"role": "user", "content": observation})
            
        # 4. FORCE CONCLUSION
        messages.append({"role": "user", "content": "Max steps reached. Based on everything above, give your final answer to the user now. Use FINAL_ANSWER."})
        final_response = self.llm._generate_blocking(messages, self.llm.PRIMARY_MODEL)
        
        action_input = self._extract(final_response, "Action Input:")
        if action_input:
            return action_input
        return final_response.strip()

    def _extract(self, text: str, prefix: str) -> str:
        """Helper to extract values like 'Action: x' from the LLM response."""
        for line in text.split('\n'):
            line_str = line.strip()
            if line_str.lower().startswith(prefix.lower()):
                return line_str[len(prefix):].strip()
        # Fallback regex if it spans multiple lines (mostly for Action Input)
        if prefix.lower().startswith("action input"):
            match = re.search(r'Action Input:\s*(.*)', text, re.DOTALL | re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return ""
