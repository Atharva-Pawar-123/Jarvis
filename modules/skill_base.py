"""
modules/skill_base.py — JARVIS Skill Framework Base
===================================================
Defines the base class for all dynamically loaded Agent Skills.
Any Python file in the `skills/` directory that inherits from this
class will be automatically loaded by JARVIS.
"""

from typing import Dict, Any

class JarvisSkill:
    """Base class for dynamically loaded JARVIS skills."""

    @property
    def intent_name(self) -> str:
        """The unique intent string that triggers this skill (e.g. 'tell_joke')."""
        raise NotImplementedError("Skills must define an intent_name.")

    @property
    def description(self) -> str:
        """A brief description of what this skill does."""
        return "Custom JARVIS skill."

    def handle(self, entities: Dict[str, Any], user_text: str) -> str:
        """
        Execute the skill logic.
        
        Args:
            entities: Extracted context from the LLM classifier.
            user_text: The raw spoken text.
            
        Returns:
            The string response JARVIS should speak aloud.
        """
        raise NotImplementedError("Skills must implement handle().")
