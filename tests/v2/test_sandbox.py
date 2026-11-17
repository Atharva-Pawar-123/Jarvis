"""
tests/v2/test_sandbox.py — Hardened Sandbox Tests
===================================================
Validates HardenedSandbox:
  - execute_script() runs Python code and returns output
  - Timeout enforcement (subprocess killed after deadline)
  - Environment variable stripping (GMAIL_APP_PASSWORD, AWS_*, etc.)
  - Empty code rejection
  - Script error capture (stderr, non-zero exit code)
  - Custom env vars passed through
"""

import sys
import os
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from modules.security.sandbox import HardenedSandbox, SandboxedExecutionResult


@pytest.fixture
def sandbox(tmp_path):
    return HardenedSandbox(base_scratch_dir=tmp_path / "sandbox", timeout_seconds=10)


# ── Basic Execution ──────────────────────────────────────────────────

class TestBasicExecution:

    def test_simple_print(self, sandbox):
        result = sandbox.execute_script("print('Hello from sandbox')")
        assert result.success
        assert "Hello from sandbox" in result.stdout
        assert result.exit_code == 0
        assert not result.timeout

    def test_math_computation(self, sandbox):
        result = sandbox.execute_script("print(42 * 100 + 7)")
        assert result.success
        assert "4207" in result.stdout

    def test_multiline_script(self, sandbox):
        code = """
import math
result = math.sqrt(144)
print(f"sqrt(144) = {result}")
"""
        result = sandbox.execute_script(code)
        assert result.success
        assert "12.0" in result.stdout


# ── Error Handling ───────────────────────────────────────────────────

class TestErrorHandling:

    def test_syntax_error_captured(self, sandbox):
        result = sandbox.execute_script("def oops(")
        assert not result.success
        assert result.exit_code != 0
        assert "SyntaxError" in result.stderr

    def test_runtime_error_captured(self, sandbox):
        result = sandbox.execute_script("x = 1/0")
        assert not result.success
        assert "ZeroDivisionError" in result.stderr

    def test_empty_code_rejected(self, sandbox):
        result = sandbox.execute_script("")
        assert not result.success
        assert "empty" in result.stderr.lower()

    def test_whitespace_only_rejected(self, sandbox):
        result = sandbox.execute_script("   \n\n  ")
        assert not result.success
        assert "empty" in result.stderr.lower()


# ── Timeout Enforcement ──────────────────────────────────────────────

class TestTimeout:

    def test_timeout_kills_process(self, tmp_path):
        sandbox = HardenedSandbox(base_scratch_dir=tmp_path / "sandbox", timeout_seconds=2)
        code = "import time; time.sleep(30); print('should not reach here')"
        result = sandbox.execute_script(code)
        assert not result.success
        assert result.timeout
        assert "timed out" in result.stderr.lower()
        assert "should not reach here" not in result.stdout


# ── Environment Variable Stripping ───────────────────────────────────

class TestEnvironmentStripping:

    def test_gmail_password_stripped(self, sandbox):
        """GMAIL_APP_PASSWORD should NOT be visible in sandboxed subprocess."""
        with patch.dict(os.environ, {"GMAIL_APP_PASSWORD": "supersecret123"}):
            code = """
import os
val = os.environ.get('GMAIL_APP_PASSWORD', 'NOT_FOUND')
print(f'GMAIL_APP_PASSWORD={val}')
"""
            result = sandbox.execute_script(code)
            assert result.success
            assert "supersecret123" not in result.stdout
            assert "NOT_FOUND" in result.stdout

    def test_aws_keys_stripped(self, sandbox):
        with patch.dict(os.environ, {
            "AWS_ACCESS_KEY_ID": "AKIA_FAKE",
            "AWS_SECRET_ACCESS_KEY": "wJalrXUtnFEMI/FAKE"
        }):
            code = """
import os
print(os.environ.get('AWS_ACCESS_KEY_ID', 'STRIPPED'))
print(os.environ.get('AWS_SECRET_ACCESS_KEY', 'STRIPPED'))
"""
            result = sandbox.execute_script(code)
            assert result.success
            assert "AKIA_FAKE" not in result.stdout
            assert "wJalrXUtnFEMI" not in result.stdout

    def test_token_wildcard_stripped(self, sandbox):
        """Any env var containing TOKEN, SECRET, PASSWORD should be stripped."""
        with patch.dict(os.environ, {
            "MY_CUSTOM_TOKEN": "token_val",
            "SOME_SECRET_KEY": "secret_val",
            "DB_PASSWORD": "pass_val"
        }):
            code = """
import os
print(os.environ.get('MY_CUSTOM_TOKEN', 'GONE'))
print(os.environ.get('SOME_SECRET_KEY', 'GONE'))
print(os.environ.get('DB_PASSWORD', 'GONE'))
"""
            result = sandbox.execute_script(code)
            assert result.success
            assert "token_val" not in result.stdout
            assert "secret_val" not in result.stdout
            assert "pass_val" not in result.stdout

    def test_path_survives_stripping(self, sandbox):
        """PATH and SYSTEMROOT must survive for subprocess to run."""
        code = """
import os
print('PATH_EXISTS:', bool(os.environ.get('PATH', '')))
"""
        result = sandbox.execute_script(code)
        assert result.success
        assert "PATH_EXISTS: True" in result.stdout


# ── Custom Environment Variables ─────────────────────────────────────

class TestCustomEnvVars:

    def test_custom_vars_injected(self, sandbox):
        code = """
import os
print(os.environ.get('MY_TEST_VAR', 'missing'))
"""
        result = sandbox.execute_script(code, env_vars={"MY_TEST_VAR": "injected_value"})
        assert result.success
        assert "injected_value" in result.stdout


# ── Result Object ────────────────────────────────────────────────────

class TestResultObject:

    def test_to_dict(self, sandbox):
        result = sandbox.execute_script("print('ok')")
        d = result.to_dict()
        assert isinstance(d, dict)
        assert "success" in d
        assert "stdout" in d
        assert "stderr" in d
        assert "exit_code" in d
        assert "timeout" in d
