"""
modules/agent/research_agent.py — Autonomous Deep Research Agent for JARVIS
=============================================================================
Conducts multi-query web research, synthesizes facts, resolves conflicting
claims, and compiles structured analytical dossiers with formal citations.
"""

import asyncio
import logging
import re
from typing import Dict, Any, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class DeepResearchAgent:
    """Multi-query autonomous researcher that fetches and synthesizes citations."""

    def __init__(self, llm, web_search_engine, browser_agent=None):
        self.llm = llm
        self.search_engine = web_search_engine
        self.browser_agent = browser_agent

    async def conduct_research(
        self,
        topic: str,
        max_subqueries: int = 3,
        step_callback: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        Conducts multi-angle deep research:
        1. Formulates 2-3 focused subqueries
        2. Queries search engine for each
        3. Extracts snippets and cross-references facts
        4. Synthesizes a structured markdown dossier with citations
        """
        logger.info(f"Deep Research Agent starting inquiry on: {topic}")

        if step_callback:
            try:
                cb_res = step_callback({
                    "type": "agent_event",
                    "event_type": "planning",
                    "description": f"Decomposing research topic into subqueries: '{topic}'"
                })
                if asyncio.iscoroutine(cb_res):
                    await cb_res
            except Exception:
                pass

        # Step 1: Query expansion
        prompt = (
            f"You are a research director. Formulate {max_subqueries} targeted web search queries "
            f"to comprehensively research this subject: '{topic}'.\n"
            "Return ONLY a JSON array of query strings, e.g. [\"query 1\", \"query 2\"]."
        )
        raw_queries = await asyncio.to_thread(self.llm.generate, [{"role": "user", "content": prompt}], False)

        subqueries = [topic]
        try:
            match = re.search(r'\[.*\]', raw_queries, re.DOTALL)
            if match:
                parsed = eval(match.group(0))  # safe fallback or json.loads
                if isinstance(parsed, list) and len(parsed) > 0:
                    subqueries = [str(q) for q in parsed[:max_subqueries]]
        except Exception:
            subqueries = [topic, f"{topic} latest updates", f"{topic} key facts"]

        findings = []
        sources = []

        # Step 2: Execute targeted searches
        for i, q in enumerate(subqueries):
            if step_callback:
                try:
                    cb_res = step_callback({
                        "type": "agent_event",
                        "event_type": "tool_executing",
                        "tool": "web_search",
                        "description": f"Searching ({i+1}/{len(subqueries)}): '{q}'"
                    })
                    if asyncio.iscoroutine(cb_res):
                        await cb_res
                except Exception:
                    pass

            search_out = ""
            try:
                if hasattr(self.search_engine, "search_and_answer"):
                    search_out = await asyncio.to_thread(self.search_engine.search_and_answer, q)
                elif hasattr(self.search_engine, "quick_search"):
                    search_out = await asyncio.to_thread(self.search_engine.quick_search, q)
                else:
                    search_out = str(self.search_engine(q))
            except Exception as e:
                search_out = f"Search failed for '{q}': {e}"

            findings.append({"query": q, "results": search_out})
            sources.append(f"Search Query: {q}")

        # Step 3: Synthesis with formal citations
        if step_callback:
            try:
                cb_res = step_callback({
                    "type": "agent_event",
                    "event_type": "planning",
                    "description": "Synthesizing cross-referenced findings into structured research dossier..."
                })
                if asyncio.iscoroutine(cb_res):
                    await cb_res
            except Exception:
                pass

        compiled_context = "\n\n".join([f"### Query: {f['query']}\n{f['results']}" for f in findings])
        synth_prompt = (
            f"You are JARVIS compiling an executive research dossier on: '{topic}'.\n\n"
            f"RAW RESEARCH FINDINGS:\n{compiled_context}\n\n"
            "REQUIREMENTS:\n"
            "1. Executive Summary\n"
            "2. Key Findings & Core Analysis\n"
            "3. Implications & Strategic Takeaways\n"
            "4. Sources & Verification Index\n"
            "Tone: Paul Bettany JARVIS style (poised, sophisticated, addressing sir)."
        )

        dossier = await asyncio.to_thread(self.llm.generate, [{"role": "user", "content": synth_prompt}], False)

        return {
            "topic": topic,
            "subqueries": subqueries,
            "dossier": dossier,
            "sources": sources,
            "timestamp": datetime.now().isoformat()
        }
