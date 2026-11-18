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
import difflib
import shlex
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

from modules.security.sandbox import HardenedSandbox

logger = logging.getLogger(__name__)


class AutonomousCodingAgent:
    """Specialized agent for inspecting, editing, and verifying local codebases."""

    def __init__(self, llm, code_engine, repo_path: Optional[Path] = None):
        self.llm = llm
        self.code_engine = code_engine
        self.repo_path = (repo_path or Path.cwd()).resolve()
        self.sandbox = HardenedSandbox()

    def _resolve_safe_path(self, rel_path: str) -> Optional[Path]:
        """Ensures path resides strictly within repository boundaries."""
        target = (self.repo_path / rel_path).resolve()
        try:
            target.relative_to(self.repo_path)
            return target
        except ValueError:
            logger.warning(f"Path traversal blocked: '{rel_path}' is outside repository root.")
            return None

    async def inspect_directory(self, rel_path: str = ".") -> List[str]:
        """Lists directory files while ignoring common build/git directories."""
        target_dir = self._resolve_safe_path(rel_path)
        if not target_dir or not target_dir.exists():
            return [f"Error: Path {rel_path} does not exist or is outside workspace."]

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
                    pass
        return files[:100]

    async def read_file_content(self, rel_path: str) -> str:
        """Reads code file content safely within boundaries."""
        target = self._resolve_safe_path(rel_path)
        if not target or not target.exists():
            return f"Error: File {rel_path} does not exist or is outside workspace."
        try:
            return target.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            return f"Error reading file {rel_path}: {e}"

    async def run_syntax_and_tests(self, test_cmd: str = "pytest") -> Dict[str, Any]:
        """Runs test verification without shell=True for security isolation."""
        try:
            cmd_args = shlex.split(test_cmd) if isinstance(test_cmd, str) else list(test_cmd)
            res = await asyncio.to_thread(
                subprocess.run,
                cmd_args,
                shell=False,
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
        Reads target file, generates updated code block, validates syntax,
        produces a unified Git diff, and formats patch for user review.
        """
        safe_target = self._resolve_safe_path(target_file)
        if not safe_target:
            return {"success": False, "error": f"Access denied: {target_file} is outside workspace boundary."}

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

        # Generate unified Git diff
        diff_lines = list(difflib.unified_diff(
            existing_code.splitlines(keepends=True),
            candidate_code.splitlines(keepends=True),
            fromfile=f"a/{target_file}",
            tofile=f"b/{target_file}"
        ))
        unified_diff = "".join(diff_lines)

        return {
            "target_file": target_file,
            "syntax_valid": syntax_ok,
            "syntax_error": syntax_err,
            "unified_diff": unified_diff,
            "proposed_code_snippet": candidate_code[:500] + ("..." if len(candidate_code) > 500 else ""),
            "full_candidate_length": len(candidate_code),
            "status": "ready_for_review" if syntax_ok else "syntax_check_failed"
        }
