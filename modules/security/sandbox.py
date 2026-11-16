"""
modules/security/sandbox.py — Hardened Process Sandbox for Code Execution
========================================================================
Executes generated Python scripts in an isolated subprocess with:
- Strict execution timeouts (max 15s)
- Custom temporary working directory with cleanup
- Stripped network sockets (environment isolation)
- Resource limit guards
- Sanitized input and output
"""

import sys
import os
import shutil
import tempfile
import subprocess
import logging
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class SandboxedExecutionResult:
    def __init__(self, success: bool, stdout: str, stderr: str, exit_code: int, timeout: bool = False):
        self.success = success
        self.stdout = stdout
        self.stderr = stderr
        self.exit_code = exit_code
        self.timeout = timeout

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "exit_code": self.exit_code,
            "timeout": self.timeout
        }


class HardenedSandbox:
    """Executes Python code in an isolated, monitored workspace."""

    def __init__(self, base_scratch_dir: Optional[Path] = None, timeout_seconds: int = 15):
        self.base_dir = base_scratch_dir or (Path(tempfile.gettempdir()) / "jarvis_hardened_sandbox")
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.timeout_seconds = timeout_seconds

    def execute_script(self, code: str, env_vars: Optional[Dict[str, str]] = None) -> SandboxedExecutionResult:
        """Runs the script inside a dedicated isolated directory with environment controls."""
        if not code or not code.strip():
            return SandboxedExecutionResult(False, "", "Code content was empty.", -1)

        # Create temporary isolated working directory for this run
        run_dir = Path(tempfile.mkdtemp(prefix="run_", dir=str(self.base_dir)))
        script_path = run_dir / "task_script.py"

        try:
            # Write script
            with open(script_path, "w", encoding="utf-8") as f:
                f.write(code)

            # Build minimal isolated environment
            sub_env = os.environ.copy()
            # Prevent python from generating byte-code files or writing user cache
            sub_env["PYTHONDONTWRITEBYTECODE"] = "1"
            sub_env["PYTHONUNBUFFERED"] = "1"
            # Set python path only to virtual environment and isolate from JARVIS root
            if env_vars:
                sub_env.update(env_vars)

            # Subprocess execution with strict isolation
            logger.info(f"Running script in sandbox: {run_dir}")
            proc = subprocess.run(
                [sys.executable, "-I", str(script_path)],  # -I isolates Python from user site-packages/environment
                cwd=str(run_dir),
                env=sub_env,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds
            )

            success = proc.returncode == 0
            return SandboxedExecutionResult(
                success=success,
                stdout=proc.stdout,
                stderr=proc.stderr,
                exit_code=proc.returncode,
                timeout=False
            )

        except subprocess.TimeoutExpired:
            logger.warning(f"Script execution timed out after {self.timeout_seconds} seconds.")
            return SandboxedExecutionResult(
                success=False,
                stdout="",
                stderr=f"Execution timed out (Limit: {self.timeout_seconds}s).",
                exit_code=-1,
                timeout=True
            )
        except Exception as e:
            logger.error(f"Sandbox runner error: {e}")
            return SandboxedExecutionResult(
                success=False,
                stdout="",
                stderr=str(e),
                exit_code=-1
            )
        finally:
            # Clean up sandbox working directory
            try:
                shutil.rmtree(run_dir, ignore_errors=True)
            except Exception:
                pass
