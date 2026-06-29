"""
modules/skill_loader.py — JARVIS Dynamic Skill Loader
=====================================================
Scans the `skills/` directory at startup and dynamically loads
any classes inheriting from JarvisSkill. Allows plug-and-play
extensibility without touching the core engine.
"""

import sys
import importlib.util
import inspect
import logging
from pathlib import Path
from typing import Dict, List

import config
from modules.skill_base import JarvisSkill

logger = logging.getLogger(__name__)

class SkillLoader:
    def __init__(self) -> None:
        self.skills: Dict[str, JarvisSkill] = {}
        self.skills_dir = Path(config.BASE_DIR) / "skills"
        
        if not self.skills_dir.exists():
            self.skills_dir.mkdir(parents=True, exist_ok=True)
            
        self._load_all_skills()

    def _load_all_skills(self) -> None:
        """Scan the skills directory and load all valid JarvisSkill classes."""
        logger.info(f"Scanning for dynamic skills in {self.skills_dir}...")
        
        # Add skills dir to path for inner imports
        if str(self.skills_dir) not in sys.path:
            sys.path.insert(0, str(self.skills_dir))
            
        for filepath in self.skills_dir.glob("*.py"):
            if filepath.name.startswith("__"):
                continue
                
            module_name = filepath.stem
            try:
                spec = importlib.util.spec_from_file_location(module_name, filepath)
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    
                    for name, obj in inspect.getmembers(module):
                        if inspect.isclass(obj) and issubclass(obj, JarvisSkill) and obj is not JarvisSkill:
                            skill_instance = obj()
                            intent = skill_instance.intent_name
                            self.skills[intent] = skill_instance
                            logger.info(f"Loaded skill: {intent} (from {module_name}.py)")
            except Exception as e:
                logger.error(f"Failed to load skill from {filepath.name}: {e}")
                
        logger.info(f"Total dynamic skills loaded: {len(self.skills)}")

    def get_dynamic_intents(self) -> List[str]:
        """Return a list of all dynamically loaded intents."""
        return list(self.skills.keys())

    def handle_intent(self, intent: str, entities: dict, user_text: str) -> str:
        """Route an intent to the appropriate dynamic skill."""
        if intent in self.skills:
            try:
                return self.skills[intent].handle(entities, user_text)
            except Exception as e:
                logger.error(f"Skill execution failed for {intent}: {e}")
                return f"I encountered an error executing the {intent} skill, sir."
        return "Unknown skill."
