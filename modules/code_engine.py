"""
modules/code_engine.py — JARVIS Local Code Execution Engine
===========================================================
Extracts Python code blocks from LLM responses, sanitizes them,
and executes them safely using the HardenedSandbox.
"""

import logging
import re
from pathlib import Path
from modules.security.sandbox import HardenedSandbox

logger = logging.getLogger(__name__)


class CodeEngine:
    def __init__(self, timeout: int = 15):
        self.sandbox = HardenedSandbox(timeout_seconds=timeout)

    def extract_code(self, text: str) -> str:
        """Extracts the first python code block from a markdown string."""
        match = re.search(r'```python\n(.*?)\n```', text, re.DOTALL)
        if match:
            return match.group(1).strip()
        match = re.search(r'```\n(.*?)\n```', text, re.DOTALL)
        if match:
            return match.group(1).strip()
        return ""

    def execute_python(self, code: str) -> dict:
        """Runs python code inside the isolated HardenedSandbox."""
        if not code:
            return {"success": False, "output": "No code provided to execute.", "error": "Empty code."}

        res = self.sandbox.execute_script(code)
        output = res.stdout if res.success else f"{res.stdout}\n{res.stderr}".strip()
        return {
            "success": res.success,
            "output": output,
            "error": res.stderr if not res.success else "",
            "timeout": res.timeout
        }
