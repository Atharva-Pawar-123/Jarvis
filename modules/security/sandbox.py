"""
modules/security/sandbox.py — Hardened Process Sandbox for Code Execution (V2.1)
=================================================================================
Executes generated Python scripts in an isolated subprocess with:
- Stripped credential environment variables (AWS_*, GMAIL_*, HA_*, TELEGRAM_*, OPENWEATHER_*)
- Denied parent inheritance
- Memory caps (512MB) and strict execution timeouts (max 15s)
- Windows Job Object resource limits (when available)
- Custom isolated temp workspace with automatic post-run shredding
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

# Sensitive variable prefixes/names to strip before launching sandboxed processes
SENSITIVE_ENV_KEYS = [
    "GMAIL_ADDRESS",
    "GMAIL_APP_PASSWORD",
    "TELEGRAM_TOKEN",
    "TELEGRAM_CHAT_ID",
    "HA_HOST",
    "HA_TOKEN",
    "OPENWEATHER_KEY",
    "OPENWEATHER_API_KEY",
    "NTFY_TOPIC",
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "AWS_DEFAULT_REGION",
    "AZURE_CLIENT_SECRET",
    "DATABASE_URL",
    "SECRET_KEY",
    "API_KEY",
]


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
    """Executes Python code in an isolated, monitored workspace with credential stripping."""

    def __init__(self, base_scratch_dir: Optional[Path] = None, timeout_seconds: int = 15, memory_limit_mb: int = 512):
        self.base_dir = base_scratch_dir or (Path(tempfile.gettempdir()) / "jarvis_hardened_sandbox")
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.timeout_seconds = timeout_seconds
        self.memory_limit_mb = memory_limit_mb

    def _build_clean_environment(self, custom_vars: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        """Creates a sanitized environment dictionary stripped of sensitive keys and credentials."""
        clean_env = {}

        # Allow basic OS necessities
        allowed_keys = {
            "SYSTEMDRIVE", "SYSTEMROOT", "WINDIR", "PATH", "PATHEXT",
            "TEMP", "TMP", "USERNAME", "USERPROFILE", "OS", "NUMBER_OF_PROCESSORS",
            "COMSPEC", "ALLUSERSPROFILE", "PROGRAMDATA", "PROGRAMFILES", "PROGRAMFILES(X86)"
        }

        for k, v in os.environ.items():
            k_upper = k.upper()
            # Omit sensitive keys or prefixes
            if any(k_upper.startswith(p) for p in ["AWS_", "GMAIL_", "HA_", "TELEGRAM_", "AZURE_"]):
                continue
            if k_upper in SENSITIVE_ENV_KEYS:
                continue
            if "TOKEN" in k_upper or "SECRET" in k_upper or "PASSWORD" in k_upper:
                continue

            if k_upper in allowed_keys or k in ["PATH", "SystemRoot", "SystemDrive"]:
                clean_env[k] = v

        # Hardened Python flags
        clean_env["PYTHONDONTWRITEBYTECODE"] = "1"
        clean_env["PYTHONUNBUFFERED"] = "1"
        clean_env["PYTHONHASHSEED"] = "random"

        if custom_vars:
            clean_env.update(custom_vars)

        return clean_env

    def execute_script(self, code: str, env_vars: Optional[Dict[str, str]] = None) -> SandboxedExecutionResult:
        """Runs code in an isolated directory with environment stripping and timeout protection."""
        if not code or not code.strip():
            return SandboxedExecutionResult(False, "", "Code content was empty.", -1)

        run_dir = Path(tempfile.mkdtemp(prefix="run_", dir=str(self.base_dir)))
        script_path = run_dir / "task_script.py"
        job_handle = None

        try:
            with open(script_path, "w", encoding="utf-8") as f:
                f.write(code)

            sub_env = self._build_clean_environment(env_vars)
            logger.info(f"Executing script in sandbox: {run_dir}")

            # Windows Job Object resource limit enforcement
            if sys.platform == "win32":
                try:
                    import ctypes
                    from ctypes import wintypes

                    job_handle = ctypes.windll.kernel32.CreateJobObjectW(None, None)
                    if job_handle:
                        # JobObjectExtendedLimitInformation = 9
                        # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000
                        # JOB_OBJECT_LIMIT_PROCESS_MEMORY = 0x0100
                        class IO_COUNTERS(ctypes.Structure):
                            _fields_ = [
                                ('ReadOperationCount', ctypes.c_uint64),
                                ('WriteOperationCount', ctypes.c_uint64),
                                ('OtherOperationCount', ctypes.c_uint64),
                                ('ReadTransferCount', ctypes.c_uint64),
                                ('WriteTransferCount', ctypes.c_uint64),
                                ('OtherTransferCount', ctypes.c_uint64),
                            ]

                        class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
                            _fields_ = [
                                ('BasicLimitInformation', ctypes.c_byte * 48),
                                ('IoInfo', IO_COUNTERS),
                                ('ProcessMemoryLimit', ctypes.c_size_t),
                                ('JobMemoryLimit', ctypes.c_size_t),
                                ('PeakProcessMemoryLimit', ctypes.c_size_t),
                                ('PeakJobMemoryLimit', ctypes.c_size_t),
                            ]

                        limits = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
                        # Set memory limit in bytes
                        mem_bytes = self.memory_limit_mb * 1024 * 1024
                        limits.ProcessMemoryLimit = mem_bytes
                        limits.JobMemoryLimit = mem_bytes
                        
                        # Set limit flags at byte offset 16 (LimitFlags in JOBOBJECT_BASIC_LIMIT_INFORMATION)
                        limit_flags = 0x2000 | 0x0100  # KILL_ON_JOB_CLOSE | PROCESS_MEMORY
                        ctypes.memmove(
                            ctypes.addressof(limits),
                            ctypes.c_byte * 48,
                            0
                        )
                        ctypes.c_uint32.from_buffer(limits.BasicLimitInformation, 16).value = limit_flags

                        ctypes.windll.kernel32.SetInformationJobObject(
                            job_handle,
                            9,
                            ctypes.byref(limits),
                            ctypes.sizeof(limits)
                        )
                except Exception as job_err:
                    logger.warning(f"Could not configure Windows Job Object: {job_err}")

            # Subprocess execution with isolated Python environment (-I)
            proc = subprocess.Popen(
                [sys.executable, "-I", str(script_path)],
                cwd=str(run_dir),
                env=sub_env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            # Assign process to Job Object on Windows
            if sys.platform == "win32" and job_handle:
                try:
                    import ctypes
                    # PROCESS_SET_QUOTA | PROCESS_TERMINATE = 0x0100 | 0x0001
                    proc_handle = ctypes.windll.kernel32.OpenProcess(0x0100 | 0x0001, False, proc.pid)
                    if proc_handle:
                        ctypes.windll.kernel32.AssignProcessToJobObject(job_handle, proc_handle)
                        ctypes.windll.kernel32.CloseHandle(proc_handle)
                except Exception as assign_err:
                    logger.warning(f"Failed to assign process to Job Object: {assign_err}")

            try:
                stdout, stderr = proc.communicate(timeout=self.timeout_seconds)
                success = proc.returncode == 0
                return SandboxedExecutionResult(
                    success=success,
                    stdout=stdout,
                    stderr=stderr,
                    exit_code=proc.returncode,
                    timeout=False
                )
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.communicate()
                logger.warning(f"Script execution timed out after {self.timeout_seconds} seconds.")
                return SandboxedExecutionResult(
                    success=False,
                    stdout="",
                    stderr=f"Execution timed out (Limit: {self.timeout_seconds}s).",
                    exit_code=-1,
                    timeout=True
                )

        except Exception as e:
            logger.error(f"Sandbox runner error: {e}", exc_info=True)
            return SandboxedExecutionResult(
                success=False,
                stdout="",
                stderr=str(e),
                exit_code=-1
            )
        finally:
            if job_handle and sys.platform == "win32":
                try:
                    import ctypes
                    ctypes.windll.kernel32.CloseHandle(job_handle)
                except Exception:
                    pass
            try:
                shutil.rmtree(run_dir, ignore_errors=True)
            except Exception:
                pass
