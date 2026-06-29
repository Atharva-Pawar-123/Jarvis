"""
modules/search_engine.py — JARVIS Ultra-Fast Search
===================================================
Provides instantaneous regex search capabilities across large codebases
by wrapping 'rg' (ripgrep) via subprocess. If ripgrep is not installed
on the host machine, it falls back to a built-in Python recursive search.
"""

import logging
import re
import subprocess
from pathlib import Path
from typing import Optional

import config

logger = logging.getLogger(__name__)


class SearchEngine:
    def __init__(self) -> None:
        self.has_ripgrep = self._check_ripgrep()
        if self.has_ripgrep:
            logger.info("Ultra-fast search enabled (ripgrep detected).")
        else:
            logger.warning("ripgrep not found. Falling back to native Python search (slower).")

    def _check_ripgrep(self) -> bool:
        """Check if 'rg' is installed and accessible in the system PATH."""
        try:
            result = subprocess.run(
                ["rg", "--version"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False
            )
            return result.returncode == 0
        except FileNotFoundError:
            return False

    def search_codebase(self, query: str, search_path: Optional[str] = None) -> str:
        """
        Search the codebase for the exact query or regex pattern.
        Returns a formatted string of results.
        """
        target_dir = search_path or str(config.BASE_DIR)
        
        if self.has_ripgrep:
            return self._search_ripgrep(query, target_dir)
        else:
            return self._search_python(query, target_dir)

    def _search_ripgrep(self, query: str, target_dir: str) -> str:
        """Execute ripgrep via subprocess."""
        try:
            # -i (case-insensitive), -n (line numbers), --no-heading (parseable output)
            result = subprocess.run(
                ["rg", "-i", "-n", "--no-heading", "--max-count=50", query, target_dir],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False
            )
            
            if result.returncode == 0:
                output = result.stdout.strip()
                lines = output.split('\n')
                if len(lines) > 50:
                    return "\n".join(lines[:50]) + f"\n\n... and {len(lines) - 50} more matches."
                return output
            elif result.returncode == 1:
                return f"No matches found for '{query}' in {target_dir}."
            else:
                return f"Ripgrep error: {result.stderr.strip()}"
                
        except Exception as exc:
            logger.error(f"Search failed: {exc}")
            return f"Search encountered an error: {exc}"

    def _search_python(self, query: str, target_dir: str) -> str:
        """Fallback Python search for machines without ripgrep."""
        matches = []
        pattern = re.compile(re.escape(query), re.IGNORECASE)
        base = Path(target_dir)
        
        # Avoid common heavy directories
        ignore_dirs = {".git", "venv", "node_modules", "__pycache__", ".pytest_cache"}
        
        try:
            for filepath in base.rglob("*"):
                # Skip ignored directories
                if any(ignored in filepath.parts for ignored in ignore_dirs):
                    continue
                    
                if filepath.is_file():
                    try:
                        # Attempt to read as text
                        with open(filepath, "r", encoding="utf-8") as f:
                            for line_num, line in enumerate(f, 1):
                                if pattern.search(line):
                                    matches.append(f"{filepath}:{line_num}:{line.strip()}")
                                    if len(matches) >= 50:
                                        break
                    except UnicodeDecodeError:
                        # Skip binary files
                        continue
                    if len(matches) >= 50:
                        break
                        
            if not matches:
                return f"No matches found for '{query}' in {target_dir}."
                
            result = "\n".join(matches)
            if len(matches) >= 50:
                result += "\n\n... results truncated at 50 matches."
            return result
            
        except Exception as exc:
            logger.error(f"Native search failed: {exc}")
            return f"Search encountered an error: {exc}"
