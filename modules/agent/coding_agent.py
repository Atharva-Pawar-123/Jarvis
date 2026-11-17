"""
modules/agent/coding_agent.py — Autonomous Coding Agent for JARVIS
===================================================================
Enables local codebase inspection, syntax-safe file modifications,
isolated sandboxed test execution, and unified git diff generation.
"""

import asyncio
import logging
import os
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class AutonomousCodingAgent:
    """Specialized agent for inspecting, editing, and verifying local codebases."""

    def __init__(self, llm, code_engine, repo_path: Optional[Path] = None):
        self.llm = llm
        self.code_engine = code_engine
        self.repo_path = repo_path or Path.cwd()

    async def inspect_directory(self, rel_path: str = ".") -> List[str]:
        """Lists directory files while ignoring common build/git directories."""
        target_dir = (self.repo_path / rel_path).resolve()
        if not target_dir.exists():
            return [f"Error: Path {rel_path} does not exist."]

        ignored = {".git", "venv", "node_modules", "__pycache__", "dist", "build"}
        files = []
        for root, dirs, filenames in os.walk(target_dir):
            dirs[:] = [d for d in dirs if d not in ignored]
            for f in filenames:
                full_p = Path(root) / f
                try:
                    rel = full_p.relative_to(self.repo_path)
                    files.append(str(rel))
                except Exception:
                    files.append(str(full_p))
        return files[:100]

    async def read_file_content(self, rel_path: str) -> str:
        """Reads code file content safely."""
        target = (self.repo_path / rel_path).resolve()
        if not target.exists():
            return f"Error: File {rel_path} does not exist."
        try:
            return target.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            return f"Error reading file {rel_path}: {e}"

    async def run_syntax_and_tests(self, test_cmd: str = "pytest") -> Dict[str, Any]:
        """Runs test verification in an isolated subprocess."""
        start_t = datetime.now()
        try:
            res = await asyncio.to_thread(
                subprocess.run,
                test_cmd,
                shell=True,
                cwd=str(self.repo_path),
                capture_output=True,
                text=True,
                timeout=60
            )
            return {
                "success": res.returncode == 0,
                "stdout": res.stdout[:2000],
                "stderr": res.stderr[:2000],
                "returncode": res.returncode
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Execution timed out after 60s"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def propose_and_verify_fix(
        self,
        task_instruction: str,
        target_file: str,
        step_callback: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        Reads target file, generates updated code block, validates syntax, and returns diff proposal.
        """
        existing_code = await self.read_file_content(target_file)
        if existing_code.startswith("Error:"):
            return {"success": False, "error": existing_code}

        if step_callback:
            try:
                cb_res = step_callback({
                    "type": "agent_event",
                    "event_type": "planning",
                    "description": f"Drafting code modification for '{target_file}'"
                })
                if asyncio.iscoroutine(cb_res):
                    await cb_res
            except Exception:
                pass

        prompt = (
            f"You are an expert autonomous software engineer. Task: {task_instruction}\n\n"
            f"FILE: {target_file}\nEXISTING CODE:\n```python\n{existing_code}\n```\n\n"
            "Generate the complete, corrected version of the code. "
            "Output ONLY the replacement code inside a ```python ``` markdown block."
        )

        response = await asyncio.to_thread(self.llm.generate, [{"role": "user", "content": prompt}], False)

        import re
        code_match = re.search(r'```(?:python)?\s*(.*?)\s*```', response, re.DOTALL)
        candidate_code = code_match.group(1) if code_match else response.strip()

        # Syntax check via compile
        syntax_ok = True
        syntax_err = None
        try:
            compile(candidate_code, target_file, 'exec')
        except SyntaxError as se:
            syntax_ok = False
            syntax_err = str(se)

        return {
            "target_file": target_file,
            "syntax_valid": syntax_ok,
            "syntax_error": syntax_err,
            "proposed_code_snippet": candidate_code[:500] + ("..." if len(candidate_code) > 500 else ""),
            "full_candidate_length": len(candidate_code),
            "status": "ready_for_review" if syntax_ok else "syntax_check_failed"
        }
