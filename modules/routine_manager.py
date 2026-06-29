"""
modules/routine_manager.py — JARVIS Routine Manager
===================================================
Loads and executes predefined sequences of intents (routines) from data/routines.json.
"""

import json
import logging
from pathlib import Path
from typing import List, Dict, Any


logger = logging.getLogger(__name__)

class RoutineManager:
    """
    Manages automated task sequences (routines).
    """

    def __init__(self, routines_path: str = "data/routines.json") -> None:
        self.path = Path(routines_path)
        self.routines: Dict[str, List[Dict[str, Any]]] = self._load()

    def _load(self) -> Dict[str, List[Dict[str, Any]]]:
        if self.path.exists():
            try:
                return json.loads(self.path.read_text(encoding="utf-8"))
            except Exception as exc:
                logger.error(f"Failed to load routines: {exc}")
        return {}

    def get_routine(self, name: str) -> List[Dict[str, Any]]:
        """
        Retrieve a routine by name (fuzzy matching).
        """
        if not name:
            return []
            
        name_lower = name.lower().replace(" ", "_")
        
        # Try exact match
        if name_lower in self.routines:
            return self.routines[name_lower]
            
        # Try partial match
        for key in self.routines:
            if name_lower in key or key in name_lower:
                logger.info(f"Fuzzy matched routine '{name}' to '{key}'")
                return self.routines[key]
                
        return []

    def list_routines(self) -> List[str]:
        return list(self.routines.keys())
