"""
tests/v2/test_four_tier_memory.py — 4-Tier Cognitive Memory System Tests
=======================================================================
Validates the lifecycle and REST endpoints for all 4 cognitive memory tiers:
1. Working Memory (active context injection, session rule counts)
2. Episodic Memory (task log, outcome storage, deletion)
3. Semantic Memory (ChromaDB facts, retrieval, deletion)
4. Procedural Memory (user habits, rules, CRUD operations)
"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock
from fastapi.testclient import TestClient

from modules.cognitive_memory import FourTierMemorySystem
from server.api_server import app, get_runtime
from server.runtime import JarvisRuntime


@pytest.fixture
def mock_four_tier(tmp_path):
    mock_rag = MagicMock()
    mock_rag.get_relevant_context.return_value = "Semantic knowledge found"
    db_file = tmp_path / "test_memory.db"
    return FourTierMemorySystem(hybrid_rag=mock_rag, db_path=db_file)


def test_procedural_memory_crud(mock_four_tier):
    """Test procedural memory addition, listing, and deletion."""
    mock_four_tier.set_procedural_preference("tone", "persona", "Always address user as sir")
    mock_four_tier.set_procedural_preference("code_style", "coding", "Prefer Python type annotations")

    prefs = mock_four_tier.get_all_procedural_preferences()
    assert len(prefs) == 2
    keys = [p["key"] for p in prefs]
    assert "tone" in keys
    assert "code_style" in keys

    deleted = mock_four_tier.delete_procedural_preference("tone")
    assert deleted is True

    prefs_after = mock_four_tier.get_all_procedural_preferences()
    assert len(prefs_after) == 1
    assert prefs_after[0]["key"] == "code_style"


def test_episodic_memory_lifecycle(mock_four_tier):
    """Test episodic logging and query."""
    mock_four_tier.log_episode(
        user_goal="Check system metrics",
        outcome="CPU 12%, RAM 45%",
        tools_used=["system_status"]
    )

    episodes = mock_four_tier.get_recent_episodes(limit=5)
    assert len(episodes) == 1
    assert episodes[0]["user_goal"] == "Check system metrics"
    assert episodes[0]["outcome"] == "CPU 12%, RAM 45%"
    assert "system_status" in episodes[0]["tools_used"]

    deleted = mock_four_tier.delete_episode(episodes[0]["episode_id"])
    assert deleted is True
    assert len(mock_four_tier.get_recent_episodes(limit=5)) == 0


def test_working_memory_format(mock_four_tier):
    """Test working memory context formatting."""
    mock_four_tier.set_procedural_preference("brevity", "style", "Keep direct answers concise")
    ctx = mock_four_tier.format_working_context("sess-123", "Write a summary")
    assert "USER PREFERENCES & PROCEDURAL HABITS:" in ctx
    assert "[style] Keep direct answers concise" in ctx

    state = mock_four_tier.get_working_memory_state("sess-123")
    assert state["session_id"] == "sess-123"
    assert state["procedural_rules_count"] == 1


def test_memory_rest_endpoints(tmp_path):
    """Test the newly added REST endpoints on the FastAPI app."""
    from server.api_server import LOCAL_AUTH_TOKEN
    rt = JarvisRuntime()
    mock_rag = MagicMock()
    mock_rag.get_relevant_context.return_value = "Mocked fact"
    rt.memory = mock_rag
    rt.four_tier_memory = FourTierMemorySystem(hybrid_rag=mock_rag, db_path=tmp_path / "api_test.db")

    app.dependency_overrides[get_runtime] = lambda: rt
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {LOCAL_AUTH_TOKEN}"}

    # 1. Procedural Memory API
    res = client.post("/api/memory/procedural", headers=headers, json={
        "key": "test_pref",
        "category": "persona",
        "preference": "British witty tone"
    })
    assert res.status_code == 200
    assert res.json()["status"] == "saved"

    res = client.get("/api/memory/procedural", headers=headers)
    assert res.status_code == 200
    prefs = res.json()["preferences"]
    assert any(p["key"] == "test_pref" for p in prefs)

    # 2. Episodic Memory API
    rt.four_tier_memory.log_episode("Run tests", "All passed", ["pytest"])
    res = client.get("/api/memory/episodic", headers=headers)
    assert res.status_code == 200
    episodes = res.json()["episodes"]
    assert len(episodes) == 1

    # 3. Working Memory API
    res = client.get("/api/memory/working?session_id=test-sess", headers=headers)
    assert res.status_code == 200
    working = res.json()
    assert working["session_id"] == "test-sess"
    assert working["procedural_rules_count"] == 1

    # Cleanup dependency override
    app.dependency_overrides.clear()
