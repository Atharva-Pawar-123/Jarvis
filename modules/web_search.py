"""
modules/web_search.py — JARVIS Web Search Engine
================================================
Handles web searching using DuckDuckGo HTML parsing (quick answers)
and opening searches directly in the default browser.
"""

import logging
import urllib.parse
import webbrowser
import requests
import re
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class WebSearchEngine:
    """
    Provides quick factual web searches and browser launching capabilities.
    """

    def __init__(self) -> None:
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }

    def search_and_answer(self, query: str) -> str:
        """Alias for quick_search to maintain compatibility with intent dispatchers."""
        return self.quick_search(query)

    def quick_search(self, query: str) -> str:
        """
        Scrape DuckDuckGo Lite HTML for the top results to provide a quick answer.
        
        Args:
            query (str): The search query.

        Returns:
            str: The top result snippet, or an error message.
        """
        if not query or not query.strip():
            return "What would you like me to search for, sir?"

        logger.info(f"Performing quick web search for: '{query}'")
        try:
            url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")
            
            # Try primary DDG lite CSS classes
            results = soup.find_all(["a", "div"], class_=re.compile(r"result__snippet"))
            
            if not results:
                # Fallback: look for general result bodies
                results = soup.find_all("td", class_="result-snippet")

            if not results:
                return f"I couldn't find any quick answers for {query}, sir."

            # Get the top 2 result snippets
            snippets = [res.text.strip() for res in results[:2]]
            
            # Combine them for the LLM to summarize, or read directly if short
            combined = " ".join(snippets)
            
            return f"Here is what I found on the web: {combined}"

        except Exception as exc:
            logger.error(f"Quick web search failed: {exc}", exc_info=True)
            return "I encountered an error while searching the web, sir."

    def open_search(self, query: str) -> str:
        """
        Open a Google search for the query in the default web browser.
        
        Args:
            query (str): The search query.

        Returns:
            str: Confirmation message.
        """
        if not query or not query.strip():
            return "What would you like me to search for, sir?"

        logger.info(f"Opening browser search for: '{query}'")
        try:
            url = f"https://www.google.com/search?q={urllib.parse.quote(query)}"
            webbrowser.open(url)
            return f"I have opened the search results for {query} on your screen, sir."
        except Exception as exc:
            logger.error(f"Browser search failed: {exc}", exc_info=True)
            return "I was unable to open the web browser, sir."
