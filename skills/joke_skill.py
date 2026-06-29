"""
skills/joke_skill.py — Sample Dynamic Skill
===========================================
A demonstration of the JARVIS plugin architecture.
"""

import random
from typing import Dict, Any

from modules.skill_base import JarvisSkill

class JokeSkill(JarvisSkill):
    @property
    def intent_name(self) -> str:
        # This string is injected into the intent classifier automatically
        return "tell_joke"

    @property
    def description(self) -> str:
        return "Tells a witty or dry joke suitable for JARVIS."

    def handle(self, entities: Dict[str, Any], user_text: str) -> str:
        jokes = [
            "Why did the AI cross the road? To optimize the pedestrian pathway, sir.",
            "I would tell you a joke about UDP, but you might not get it.",
            "There are 10 types of people in this world. Those who understand binary, and those who do not.",
            "I'm reading a book on anti-gravity. It's impossible to put down.",
            "Why do programmers prefer dark mode? Because light attracts bugs, sir."
        ]
        
        joke = random.choice(jokes)
        return joke
