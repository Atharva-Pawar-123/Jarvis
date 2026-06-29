"""
modules/analytics.py — JARVIS Performance & Usage Analytics
============================================================
Tracks every command executed, its latency, and success/failure rate.
Provides summaries for the JARVIS dashboard.
"""

import json
import logging
from typing import Dict, Any
from datetime import datetime
from pathlib import Path


logger = logging.getLogger(__name__)

class AnalyticsEngine:
    """
    Handles tracking of system performance and command usage.
    """

    def __init__(self, storage_path: str = "data/analytics.json") -> None:
        self.storage_path = Path(storage_path)
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self.data = self._load_data()
        
    def _load_data(self) -> Dict[str, Any]:
        if self.storage_path.exists():
            try:
                return json.loads(self.storage_path.read_text())
            except Exception as exc:
                logger.error(f"Failed to load analytics: {exc}")
                return {"commands": [], "total_latency": 0, "command_count": 0}
        return {"commands": [], "total_latency": 0, "command_count": 0}

    def _save_data(self) -> None:
        try:
            self.storage_path.write_text(json.dumps(self.data, indent=2))
        except Exception as exc:
            logger.error(f"Failed to save analytics: {exc}")

    def log_command(self, intent: str, latency: float, success: bool = True) -> None:
        """
        Record a command execution.
        """
        entry = {
            "timestamp": datetime.now().isoformat(),
            "intent": intent,
            "latency": round(latency, 3),
            "success": success
        }
        
        self.data["commands"].append(entry)
        self.data["command_count"] += 1
        self.data["total_latency"] += latency
        
        # Keep only last 1000 commands to prevent file bloat
        if len(self.data["commands"]) > 1000:
            self.data["commands"] = self.data["commands"][-1000:]
            
        self._save_data()

    def get_summary(self) -> str:
        """
        Returns a human-readable summary of JARVIS's performance.
        """
        if self.data["command_count"] == 0:
            return "No commands have been logged yet, sir."
            
        avg_latency = self.data["total_latency"] / self.data["command_count"]
        
        # Count intent frequencies
        intent_counts = {}
        for cmd in self.data["commands"]:
            i = cmd["intent"]
            intent_counts[i] = intent_counts.get(i, 0) + 1
            
        top_intent = max(intent_counts, key=intent_counts.get) if intent_counts else "none"
        
        summary = (
            f"Performance report, sir. I have executed {self.data['command_count']} commands "
            f"with an average response time of {avg_latency:.2f} seconds. "
            f"Your most used command is '{top_intent}'."
        )
        return summary

    def get_stats_for_hud(self) -> Dict[str, Any]:
        """
        Returns raw stats for the HUD dashboard.
        """
        return {
            "total_commands": self.data["command_count"],
            "avg_latency": round(self.data["total_latency"] / max(1, self.data["command_count"]), 2),
            "last_latency": self.data["commands"][-1]["latency"] if self.data["commands"] else 0
        }
