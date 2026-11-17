"""
modules/skills/registry.py — Dynamic Skill Registry for JARVIS (V2.1 Hardened)
==============================================================================
Discovers, validates, and loads modular skills from the `skills/` directory.
Mounts parameter schemas directly into CanonicalTool definitions so skills
receive their declared argument signatures (e.g. `expression`).
"""

import os
import json
import logging
import importlib.util
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable
from pydantic import BaseModel

import config
from modules.agent.tool_registry import StructuredToolRegistry

logger = logging.getLogger(__name__)

SKILLS_DIR = Path(config.BASE_DIR) / "skills"


class SkillManifest(BaseModel):
    name: str
    version: str = "1.0.0"
    description: str
    permissions_required: List[str] = []
    parameters_schema: Dict[str, Any] = {}
    timeout_seconds: int = 20


class DynamicSkillRegistry:
    """Discovers and registers standalone skills dynamically into the tool registry."""

    def __init__(self, skills_dir: Optional[Path] = None):
        self.skills_dir = skills_dir or SKILLS_DIR
        self.skills_dir.mkdir(parents=True, exist_ok=True)
        self.loaded_skills: Dict[str, Dict[str, Any]] = {}

    def discover_and_mount(self, tool_registry: StructuredToolRegistry):
        """Scans the skills directory, loads valid manifests, and registers canonical tools."""
        logger.info(f"Scanning skills directory: {self.skills_dir}")

        for item in self.skills_dir.iterdir():
            if item.is_dir() and not item.name.startswith((".", "_")):
                manifest_file = item / "manifest.json"
                handler_file = item / "handler.py"

                if manifest_file.exists() and handler_file.exists():
                    try:
                        with open(manifest_file, "r", encoding="utf-8") as f:
                            data = json.load(f)
                        manifest = SkillManifest(**data)

                        # Load handler dynamically
                        spec = importlib.util.spec_from_file_location(f"skill_{manifest.name}", str(handler_file))
                        mod = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(mod)

                        if hasattr(mod, "execute") and callable(mod.execute):
                            # Wrap into executor that passes unpacked params
                            def make_executor(execute_fn):
                                def _exec(*args, **kwargs):
                                    params = dict(kwargs)
                                    if args:
                                        if isinstance(args[0], dict):
                                            params.update(args[0])
                                        else:
                                            # If single positional arg, map to first required parameter or 'query'
                                            params["input"] = args[0]
                                    return execute_fn(context={}, params=params)
                                return _exec

                            # Pass declared manifest parameters_schema so LLM receives accurate signature
                            schema = manifest.parameters_schema if manifest.parameters_schema else None

                            tool_registry.register(
                                name=f"skill_{manifest.name}",
                                description=f"[Skill] {manifest.description}",
                                func=make_executor(mod.execute),
                                custom_schema=schema,
                                risk="medium" if manifest.permissions_required else "low",
                                permission_category=f"skill_{manifest.name}",
                                timeout=manifest.timeout_seconds
                            )

                            self.loaded_skills[manifest.name] = {
                                "manifest": manifest,
                                "handler": mod.execute
                            }
                            logger.info(f"Loaded dynamic skill with canonical schema: {manifest.name} v{manifest.version}")

                    except Exception as e:
                        logger.error(f"Failed to load skill at {item}: {e}")

    def list_loaded_skills(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": k,
                "version": v["manifest"].version,
                "description": v["manifest"].description,
                "permissions": v["manifest"].permissions_required,
                "parameters_schema": v["manifest"].parameters_schema
            }
            for k, v in self.loaded_skills.items()
        ]
