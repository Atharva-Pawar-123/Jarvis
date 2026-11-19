"""
modules/image_edit.py — Local Image Editing & Inpainting Engine (SD WebUI Forge)
================================================================================
Handles image-to-image (img2img), localized inpainting with masks, and instruction-guided
edits 100% locally on NVIDIA RTX GPU without cloud reliance.
"""

import os
import io
import base64
import logging
import requests
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
from PIL import Image

import config

logger = logging.getLogger(__name__)

class ImageEditEngine:
    def __init__(self):
        self.local_url = getattr(config, "SD_LOCAL_URL", "http://127.0.0.1:7860")
        self.save_dir = Path("d:/JARVIS/storage/images/edited")
        self.upload_dir = Path("d:/JARVIS/storage/images/uploaded")
        self.save_dir.mkdir(parents=True, exist_ok=True)
        self.upload_dir.mkdir(parents=True, exist_ok=True)

    def save_uploaded_image(self, file_bytes: bytes, filename: str) -> Tuple[str, str, int, int]:
        """
        Validates, strips unsafe EXIF, converts to standard sRGB, saves to disk,
        and returns (filepath, base64_str, width, height).
        """
        image = Image.open(io.BytesIO(file_bytes))
        if image.mode != "RGB":
            image = image.convert("RGB")

        # Resize if overly large to prevent GPU OOM
        max_dim = 1536
        if max(image.width, image.height) > max_dim:
            image.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)

        import datetime
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        safe_name = f"upload_{timestamp}.png"
        filepath = self.upload_dir / safe_name
        image.save(filepath, format="PNG")

        buffered = io.BytesIO()
        image.save(buffered, format="PNG")
        b64_str = base64.b64encode(buffered.getvalue()).decode("utf-8")

        return str(filepath), b64_str, image.width, image.height

    def edit_image(
        self,
        init_image_b64: str,
        prompt: str,
        mask_b64: Optional[str] = None,
        negative_prompt: str = "",
        denoising_strength: float = 0.65,
        steps: int = 20,
        cfg_scale: float = 7.0,
        sampler_name: str = "Euler a",
        model_checkpoint: Optional[str] = None
    ) -> Optional[bytes]:
        """
        Executes img2img or inpainting via local SD-Forge API (/sdapi/v1/img2img).
        """
        # Clean clean base64 data URLs if present
        if "base64," in init_image_b64:
            init_image_b64 = init_image_b64.split("base64,")[1]

        clean_mask = None
        if mask_b64:
            clean_mask = mask_b64.split("base64,")[1] if "base64," in mask_b64 else mask_b64

        # Read dimensions of init image to match aspect ratio
        try:
            im = Image.open(io.BytesIO(base64.b64decode(init_image_b64)))
            w, h = im.size
            # Cap dimensions for RTX 3050 6GB VRAM budget
            scale = min(1.0, 768 / max(w, h))
            target_w = int((w * scale) // 64) * 64
            target_h = int((h * scale) // 64) * 64
            target_w = max(384, min(1024, target_w))
            target_h = max(384, min(1024, target_h))
        except Exception:
            target_w, target_h = 512, 512

        payload: Dict[str, Any] = {
            "init_images": [init_image_b64],
            "prompt": prompt,
            "negative_prompt": negative_prompt or (
                "blurry, bad anatomy, deformed, disfigured, poorly drawn, extra limbs, watermark, text"
            ),
            "denoising_strength": float(denoising_strength),
            "steps": int(steps),
            "cfg_scale": float(cfg_scale),
            "sampler_name": sampler_name,
            "width": target_w,
            "height": target_h,
            "resize_mode": 0, # Just resize
        }

        if clean_mask:
            payload["mask"] = clean_mask
            payload["inpainting_fill"] = 1 # original
            payload["inpaint_full_res"] = True
            payload["inpaint_full_res_padding"] = 32

        headers = {"Content-Type": "application/json"}
        try:
            res = requests.post(
                f"{self.local_url}/sdapi/v1/img2img",
                json=payload,
                headers=headers,
                timeout=180
            )
            if res.status_code == 200:
                data = res.json()
                images = data.get("images", [])
                if images:
                    return base64.b64decode(images[0])
            logger.error(f"SD Forge img2img failed with status {res.status_code}: {res.text[:200]}")
            return None
        except Exception as e:
            logger.error(f"SD Forge img2img connection failed: {e}")
            return None
