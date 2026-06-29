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
import requests
from pathlib import Path
from typing import Optional

import config

logger = logging.getLogger(__name__)


class ImageGenerationEngine:
    """
    Image Generation Engine powered by Pollinations AI (Free / No Auth).
    """

    def __init__(self) -> None:
        self.save_dir = Path(config.IMAGE_SAVE_DIR)
        self.save_dir.mkdir(parents=True, exist_ok=True)
        self.api_url = "https://image.pollinations.ai/prompt/{prompt}"
        # Local AUTOMATIC1111 endpoint
        self.local_url = getattr(config, "SD_LOCAL_URL", "http://127.0.0.1:7860")

    def _generate_local(self, prompt: str) -> Optional[bytes]:
        """
        Attempt to generate an image using a local AUTOMATIC1111 instance.
        """
        try:
            payload = {
                "prompt": prompt,
                "steps": 20,
                "cfg_scale": 7,
                "width": 512,
                "height": 512,
                "sampler_name": "Euler a"
            }
            response = requests.post(url=f"{self.local_url}/sdapi/v1/txt2img", json=payload, timeout=60)
            if response.status_code == 200:
                import base64
                r = response.json()
                return base64.b64decode(r['images'][0])
        except Exception as exc:
            logger.debug(f"Local Stable Diffusion not available: {exc}")
        return None

    def enhance_prompt(self, prompt: str, llm) -> str:
        """
        Use the LLM to expand a simple prompt into a detailed Stable Diffusion prompt.
        """
        expansion_request = [
            {"role": "system", "content": "You are a prompt engineer for Stable Diffusion. Expand the user's short description into a highly detailed, artistic prompt. Include lighting, style, and composition. Keep it under 70 words."},
            {"role": "user", "content": f"Expand this: {prompt}"}
        ]
        try:
            enhanced = llm.generate(expansion_request)
            logger.info(f"Enhanced prompt: {enhanced}")
            return enhanced.strip()
        except Exception as exc:
            logger.warning(f"Prompt enhancement failed: {exc}")
            return prompt

    def generate_image(self, prompt: str, llm=None, auto_open: bool = True) -> str:
        """
        Generates an image from a text prompt and opens it.
        """
        if not prompt or not prompt.strip():
            return "Please tell me what you would like me to draw, sir."

        # Enhance prompt if LLM is available
        working_prompt = prompt
        if llm:
            working_prompt = self.enhance_prompt(prompt, llm)

        logger.info(f"Generating image with prompt: '{working_prompt}'")

        try:
            # Try Local Stable Diffusion first
            img_data = self._generate_local(working_prompt)
            source = "Local Stable Diffusion" if img_data else "Pollinations AI"

            if not img_data:
                # Fallback to Pollinations AI
                encoded_prompt = urllib.parse.quote(working_prompt.strip())
                target_url = self.api_url.format(prompt=encoded_prompt)
                response = requests.get(target_url, timeout=45)
                response.raise_for_status()
                img_data = response.content
            
            logger.info(f"Image generated via {source}.")
            
            # Use unique timestamp including milliseconds to avoid filename collision in batch
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            filename = f"generated_image_{timestamp}.jpg"
            filepath = self.save_dir / filename
            
            with open(filepath, 'wb') as f:
                f.write(img_data)
            
            if auto_open:
                os.startfile(str(filepath))
                
            return f"I have finished drawing that for you, sir. Generated via {source}."

        except Exception as exc:
            logger.error(f"Image generation failed: {exc}")
            return "I apologize, sir, but I encountered an error while trying to generate that image."

