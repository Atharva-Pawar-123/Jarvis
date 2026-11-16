"""
modules/image_gen.py — JARVIS Image Generation Engine (Pollinations AI)
=======================================================================
Generates high-quality images using the free Pollinations AI endpoint.
Saves the images locally and pops them open natively on Windows.
Requires absolutely no API keys or authentication.
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
    Image Generation Engine powered by local SD WebUI Forge (Default / Zero-Cost / Uncensored)
    with seamless fallback to Pollinations AI.
    """

    def __init__(self) -> None:
        self.save_dir = Path(config.IMAGES_DIR)
        self.save_dir.mkdir(parents=True, exist_ok=True)
        self.local_url = getattr(config, "SD_LOCAL_URL", "http://127.0.0.1:7860")
        self.api_url = "https://image.pollinations.ai/prompt/{prompt}"
        self.default_negative_prompt = (
            "(worst quality, low quality:1.4), (deformed, distorted, disfigured:1.3), "
            "poorly drawn, bad anatomy, wrong anatomy, extra limb, missing limb, "
            "floating limbs, mutated hands and fingers, disconnected limbs, mutation, "
            "watermark, signature, text, blurry"
        )
        self._ensure_forge_running()

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

    def _generate_local(self, prompt: str, negative_prompt: str = "", steps: int = 20, width: int = 512, height: int = 512) -> Optional[bytes]:
        """
        Generates an image via local Forge API at high speed on GPU.
        """
        neg = negative_prompt or self.default_negative_prompt
        try:
            payload = {
                "prompt": prompt,
                "negative_prompt": neg,
                "steps": steps,
                "cfg_scale": 7.0,
                "width": width,
                "height": height,
                "sampler_name": "Euler a"
            }
            response = requests.post(
                url=f"{self.local_url}/sdapi/v1/txt2img",
                json=payload,
                timeout=120
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
            source = "Local Stable Diffusion" if img_data else None

            # 2. Fallback to Pollinations AI if local engine is offline
            if not img_data:
                logger.info("Local engine unavailable; falling back to Pollinations AI...")
                encoded_prompt = urllib.parse.quote(working_prompt.strip())
                target_url = self.api_url.format(prompt=encoded_prompt)
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                }
                
                max_retries = 3
                for attempt in range(max_retries):
                    response = requests.get(f"{target_url}?nologo=true&model=turbo", headers=headers, timeout=60)
                    if response.status_code == 200:
                        img_data = response.content
                        source = "Pollinations AI"
                        break
                    elif response.status_code in (402, 429, 503):
                        import time
                        time.sleep(8)
                    else:
                        response.raise_for_status()

            if not img_data:
                return "I apologize, sir, but both the local and cloud image engines were unable to render that."

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

