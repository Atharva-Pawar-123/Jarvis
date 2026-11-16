"""
modules/code_engine.py — JARVIS Local Code Execution Engine
===========================================================
Extracts Python code blocks from LLM responses, safely executes them 
in a controlled subprocess, and captures stdout/stderr for self-correction.
"""

import logging
import re
import subprocess
import sys
import tempfile
import os
import uuid
from pathlib import Path

logger = logging.getLogger(__name__)

class CodeEngine:
    def __init__(self):
        self.temp_dir = Path(tempfile.gettempdir()) / "jarvis_sandbox"
        self.temp_dir.mkdir(exist_ok=True)
        self.execution_timeout = 15  # seconds

    def extract_code(self, text: str) -> str:
        """Extracts the first python code block from a markdown string."""
        match = re.search(r'```python\n(.*?)\n```', text, re.DOTALL)
        if match:
            return match.group(1).strip()
        # Fallback to generic code block
        match = re.search(r'```\n(.*?)\n```', text, re.DOTALL)
        if match:
            return match.group(1).strip()
        return ""

    def execute_python(self, code: str) -> dict:
        """Runs python code in a subprocess and returns the result."""
        if not code:
            return {"success": False, "output": "No code provided to execute.", "error": "Empty code."}

        # Write to a uniquely-named temporary file to avoid race conditions
        script_path = self.temp_dir / f"exec_{uuid.uuid4().hex[:8]}.py"
        try:
            with open(script_path, "w", encoding="utf-8") as f:
                f.write(code)
        except Exception as e:
            logger.error(f"Failed to write sandbox code: {e}")
            return {"success": False, "output": "", "error": str(e)}

        # Execute
        try:
            logger.info("Executing generated code in sandbox...")
            result = subprocess.run(
                [sys.executable, str(script_path)],
                capture_output=True,
                text=True,
                timeout=self.execution_timeout
            )
            
            success = result.returncode == 0
            return {
                "success": success,
                "output": result.stdout.strip(),
                "error": result.stderr.strip() if not success else ""
            }
            
        except subprocess.TimeoutExpired:
            logger.warning("Code execution timed out.")
            return {"success": False, "output": "", "error": f"Execution timed out after {self.execution_timeout} seconds."}
        except Exception as e:
            logger.error(f"Code execution error: {e}")
            return {"success": False, "output": "", "error": str(e)}
        finally:
            # Cleanup
            try:
                os.remove(script_path)
            except Exception:
                pass
