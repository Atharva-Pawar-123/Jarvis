"""
modules/sentiment.py — JARVIS Sentiment Analyzer
===============================================
Analyzes text sentiment to enable "emotional" TTS responses.
Uses a lightweight rule-based approach or a small model.
"""

import logging
import re

logger = logging.getLogger(__name__)

class SentimentAnalyzer:
    """
    Analyzes text to determine emotional tone.
    """

    # Simple keyword maps for emotional weighting
    POSITIVE_WORDS = {"excellent", "perfect", "great", "wonderful", "success", "congratulations", "happy", "pleasure"}
    NEGATIVE_WORDS = {"error", "failed", "warning", "critical", "danger", "sorry", "unfortunately", "bad", "problem"}
    URGENT_WORDS = {"immediately", "urgent", "now", "quick", "fast", "asap", "hurry"}

    def analyze(self, text: str) -> str:
        """
        Analyze text and return an emotion label: 'happy', 'serious', 'urgent', or 'neutral'.
        """
        if not text:
            return "neutral"
            
        text_lower = text.lower()
        words = set(re.findall(r'\w+', text_lower))
        
        if words & self.URGENT_WORDS:
            return "urgent"
        if words & self.NEGATIVE_WORDS:
            return "serious"
        if words & self.POSITIVE_WORDS:
            return "happy"
            
        return "neutral"

    def get_tts_params(self, sentiment: str) -> dict:
        """
        Map sentiment to TTS parameters (length_scale, etc.)
        """
        params = {
            "happy": {"length_scale": 0.9, "pitch": 1.1},   # Slightly faster, higher pitch
            "serious": {"length_scale": 1.1, "pitch": 0.9}, # Slower, deeper
            "urgent": {"length_scale": 0.8, "pitch": 1.05}, # Much faster
            "neutral": {"length_scale": 1.0, "pitch": 1.0}  # Default
        }
        return params.get(sentiment, params["neutral"])
