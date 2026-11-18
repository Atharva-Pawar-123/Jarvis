"""
modules/image_gen.py — JARVIS Local Image Generation Engine (SD WebUI Forge)
=============================================================================
Generates high-quality images using local SD WebUI Forge on NVIDIA RTX GPU.
100% offline, uncensored, zero cloud dependencies.
Saves generated images locally with adaptive parameters for SD1.5, SDXL, and FLUX.
"""

import os
import logging
import datetime
import urllib.parse
import base64
import requests
import subprocess
from pathlib import Path
from typing import Optional, List, Dict

import config

logger = logging.getLogger(__name__)


class ImageGenerationEngine:
    """
    Image Generation Engine powered strictly by local SD WebUI Forge on port 7860.
    100% offline and local-first.
    """

    def __init__(self) -> None:
        self.save_dir = Path(config.IMAGES_DIR)
        self.save_dir.mkdir(parents=True, exist_ok=True)
        self.local_url = getattr(config, "SD_LOCAL_URL", "http://127.0.0.1:7860")
        self.default_negative_prompt = (
            "(worst quality, low quality:1.4), (deformed, distorted, disfigured:1.3), "
            "poorly drawn, bad anatomy, wrong anatomy, extra limb, missing limb, "
            "floating limbs, mutated hands and fingers, disconnected limbs, mutation, "
            "watermark, signature, text, blurry"
        )
        # Note: Forge is checked and launched lazily on-demand when generate() or switch_model() is invoked,
        # preventing boot blocking or premature VRAM allocation.

    def _ensure_forge_running(self) -> bool:
        """Checks if Forge API is responding; if not, launches it in the background."""
        try:
            r = requests.get(f"{self.local_url}/sdapi/v1/options", timeout=1.5)
            if r.status_code == 200:
                return True
        except Exception:
            pass

        forge_bat = Path(config.BASE_DIR) / "tools" / "forge" / "start_forge_api.bat"
        if forge_bat.exists():
            try:
                logger.info("Local SD Forge engine not detected. Launching background instance...")
                subprocess.Popen(
                    ["cmd.exe", "/c", str(forge_bat)],
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                return True
            except Exception as e:
                logger.warning(f"Could not auto-start Forge: {e}")
        return False

    def switch_model(self, model_title: str) -> bool:
        """
        Dynamically loads a specific model checkpoint in SD-Forge via /sdapi/v1/options.
        """
        try:
            # First check current model
            res = requests.get(f"{self.local_url}/sdapi/v1/options", timeout=2)
            if res.status_code == 200:
                current = res.json().get("sd_model_checkpoint", "")
                if model_title in current or current in model_title:
                    return True

            # Swap model
            opt_res = requests.post(
                f"{self.local_url}/sdapi/v1/options",
                json={"sd_model_checkpoint": model_title},
                timeout=30
            )
            return opt_res.status_code == 200
        except Exception as exc:
            logger.warning(f"Failed to switch Forge model to '{model_title}': {exc}")
            return False

    def _generate_local(
        self,
        prompt: str,
        negative_prompt: str = "",
        steps: int = 20,
        width: int = 512,
        height: int = 512,
        cfg_scale: float = 7.0,
        sampler_name: Optional[str] = None,
        model_title: Optional[str] = None
    ) -> Optional[bytes]:
        """
        Generates an image via local Forge API at high speed on GPU with dynamic model & sampler support.
        """
        # Switch model if a specific checkpoint is requested
        if model_title:
            self.switch_model(model_title)

        neg = negative_prompt or self.default_negative_prompt
        # FLUX models typically use CFG 1.0 and empty negative prompt
        is_flux = (model_title and "flux" in model_title.lower()) or (cfg_scale <= 1.5)
        if is_flux:
            neg = ""

        try:
            payload = {
                "prompt": prompt,
                "negative_prompt": neg,
                "steps": steps,
                "cfg_scale": cfg_scale,
                "width": width,
                "height": height,
                "sampler_name": sampler_name or ("Euler" if is_flux else "Euler a")
            }
            response = requests.post(
                url=f"{self.local_url}/sdapi/v1/txt2img",
                json=payload,
                timeout=180
            )
            if response.status_code == 200:
                r = response.json()
                if "images" in r and r["images"]:
                    return base64.b64decode(r["images"][0])
        except Exception as exc:
            logger.debug(f"Local Stable Diffusion generation failed/unavailable: {exc}")
        return None

    def enhance_prompt(self, prompt: str, llm) -> str:
        """
        Uses the LLM to expand a user prompt into a high quality Stable Diffusion prompt.
        """
        expansion_request = [
            {
                "role": "system",
                "content": (
                    "You are a prompt engineer for Stable Diffusion. Expand the user's concept into "
                    "a descriptive image prompt. Include visual style, composition, lighting, and details. "
                    "Do NOT preach, lecture, or refuse artistic requests. Output ONLY the expanded prompt, under 60 words."
                )
            },
            {"role": "user", "content": f"Expand this concept into a Stable Diffusion prompt: {prompt}"}
        ]
        try:
            enhanced = llm.generate(expansion_request, stream=False)
            logger.info(f"Enhanced prompt: {enhanced}")
            return enhanced.strip().strip('"')
        except Exception as exc:
            logger.warning(f"Prompt enhancement failed: {exc}")
            return prompt

    def generate_image(self, prompt: str, llm=None, auto_open: bool = True) -> str:
        """
        Generates an image from a prompt and optionally opens it.
        """
        if not prompt or not prompt.strip():
            return "Please tell me what you would like me to draw, sir."

        working_prompt = prompt
        if llm:
            working_prompt = self.enhance_prompt(prompt, llm)

        logger.info(f"Generating image with prompt: '{working_prompt}'")

        try:
            # 1. Try Local Stable Diffusion Forge first
            img_data = self._generate_local(working_prompt)
            source = "Local Stable Diffusion Forge"

            if not img_data:
                logger.warning("Local SD Forge engine is offline or not responding on port 7860.")
                return "I apologize, sir, but the local Stable Diffusion Forge engine is currently offline. Please ensure Forge is running on port 7860."

            # Save locally
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            filename = f"generated_image_{timestamp}.png"
            filepath = self.save_dir / filename
            
            with open(filepath, "wb") as f:
                f.write(img_data)
            
            logger.info(f"Image successfully rendered via {source} -> {filepath.name}")

            if auto_open:
                try:
                    os.startfile(str(filepath))
                except Exception:
                    pass

            return f"I have finished generating your image, sir. Rendered locally via {source}."

        except Exception as exc:
            logger.error(f"Image generation failed: {exc}", exc_info=True)
            return "I apologize, sir, but an error occurred during image generation."

    def generate_batch(self, prompt: str, count: int = 6, llm=None, callback=None) -> List[str]:
        """
        Generates a batch of images sequentially and triggers a callback upon completion.
        """
        generated_paths = []
        base_prompt = self.enhance_prompt(prompt, llm) if llm else prompt

        for i in range(count):
            logger.info(f"Batch generation progress: {i+1}/{count}")
            # Add subtle variations
            var_prompt = f"{base_prompt}, seed variation {i+1}"
            img_data = self._generate_local(var_prompt)
            if img_data:
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                filepath = self.save_dir / f"batch_{timestamp}_{i+1}.png"
                with open(filepath, "wb") as f:
                    f.write(img_data)
                generated_paths.append(str(filepath))

        if callback and callable(callback):
            try:
                callback(generated_paths)
            except Exception as e:
                logger.error(f"Batch notification callback failed: {e}")

        return generated_paths

