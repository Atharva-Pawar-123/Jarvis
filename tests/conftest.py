"""
tests/conftest.py — Shared fixtures for JARVIS V2.1 test suite
================================================================
Provides mock LLM engines, in-memory SQLite databases, temporary
directories, and isolated tool registries that don't require GPU,
Ollama, or any external services.
"""

import sys
import os
import asyncio
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock

import pytest

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Must be set before importing config
os.environ.setdefault("JARVIS_DATA_DIR", str(PROJECT_ROOT / "data"))


@pytest.fixture
def tmp_dir(tmp_path):
    """Provides a clean temporary directory."""
    return tmp_path


@pytest.fixture
def mock_llm():
    """
    Returns a mock LLM engine that returns canned responses.
    Avoids loading any real models.
    """
    llm = MagicMock()
    llm.generate = MagicMock(return_value="Hello sir, I am JARVIS.")
    llm.pre_warm = MagicMock()
    return llm


@pytest.fixture
def tool_registry():
    """Returns a fresh StructuredToolRegistry with no tools registered."""
    from modules.agent.tool_registry import StructuredToolRegistry
    return StructuredToolRegistry()


@pytest.fixture
def permission_engine():
    """Returns a fresh PermissionEngine with default policies."""
    from modules.security.permission_engine import PermissionEngine
    return PermissionEngine()


@pytest.fixture
def task_db_path(tmp_path):
    """Returns a path for a temporary task SQLite database."""
    return tmp_path / "test_tasks.db"

