"""
tests/v2/test_advanced_intelligence.py — Advanced Intelligence Verification Suite
================================================================================
Validates:
1. Deep Research Agent (subquery generation and synthesis pipeline)
2. Autonomous Coding Agent (syntax verification, file inspection, safe compilation)
3. Document Intelligence Suite (document ingestion to memory, chunk indexing)
4. Image Generation models endpoint (explicit models list, no auto option)
"""

import pytest
import asyncio
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock
from fastapi.testclient import TestClient

from modules.agent.research_agent import DeepResearchAgent
from modules.agent.coding_agent import AutonomousCodingAgent
from modules.document_reader import DocumentReader
from modules.agent.tool_registry import (
    DeepResearchInput,
    CodeProposalInput,
    IngestDocumentInput
)
from server.api_server import app, get_runtime, LOCAL_AUTH_TOKEN
from server.runtime import JarvisRuntime


@pytest.mark.asyncio
async def test_deep_research_agent_flow():
    """Verify DeepResearchAgent query decomposition and report synthesis."""
    mock_llm = MagicMock()
    mock_llm.generate.side_effect = [
        '["quantum computing 2026", "quantum error correction breakthrough"]',  # query expansion
        '# Executive Research Dossier\nQuantum computing has achieved significant milestones...'  # synthesis
    ]

    mock_search = MagicMock()
    mock_search.search_and_answer.return_value = "Top results: 1000-qubit processors announced."

    agent = DeepResearchAgent(llm=mock_llm, web_search_engine=mock_search)
    res = await agent.conduct_research("Quantum computing progress", max_subqueries=2)

    assert res["topic"] == "Quantum computing progress"
    assert len(res["subqueries"]) == 2
    assert "quantum computing 2026" in res["subqueries"]
    assert "Executive Research Dossier" in res["dossier"]
    assert len(res["sources"]) == 2


@pytest.mark.asyncio
async def test_autonomous_coding_agent_syntax_check(tmp_path):
    """Verify AutonomousCodingAgent inspects code and catches syntax bugs."""
    test_file = tmp_path / "sample.py"
    test_file.write_text("def hello():\n    return 'world'\n", encoding="utf-8")

    mock_llm = MagicMock()
    # LLM outputs valid python
    mock_llm.generate.return_value = "```python\ndef hello(name: str = 'sir'):\n    return f'world, {name}'\n```"

    mock_code_engine = MagicMock()
    agent = AutonomousCodingAgent(llm=mock_llm, code_engine=mock_code_engine, repo_path=tmp_path)

    res = await agent.propose_and_verify_fix("Add name parameter", "sample.py")
    assert res["syntax_valid"] is True
    assert res["status"] == "ready_for_review"

    # LLM outputs broken syntax
    mock_llm.generate.return_value = "```python\ndef hello(broken syntax\n```"
    res_err = await agent.propose_and_verify_fix("Break it", "sample.py")
    assert res_err["syntax_valid"] is False
    assert res_err["status"] == "syntax_check_failed"


def test_document_intelligence_ingest_to_memory(tmp_path):
    """Verify DocumentReader reads and chunks files into ChromaDB memory."""
    doc_path = tmp_path / "notes.txt"
    doc_path.write_text("JARVIS operational protocols.\n\nSection 1: Security gates are strict.\n\nSection 2: Offline first.", encoding="utf-8")

    reader = DocumentReader()
    mock_memory = MagicMock()
    mock_memory.add_fact = MagicMock()

    chunk_count = reader.ingest_to_memory(str(doc_path), mock_memory, chunk_size=50, overlap=10)
    assert chunk_count > 0
    assert mock_memory.add_fact.call_count == chunk_count


def test_image_models_explicit_selector():
    """Verify GET /api/image/models lists available models explicitly without auto fallback."""
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {LOCAL_AUTH_TOKEN}"}
    res = client.get("/api/image/models", headers=headers)
    assert res.status_code == 200
    models = res.json()["models"]
    model_ids = [m["id"] for m in models]

    # Explicit models exist
    assert any("local" in mid or "controlnet" in mid for mid in model_ids)
    # NO auto option
    assert "auto" not in model_ids
