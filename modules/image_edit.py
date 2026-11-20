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
from PIL import Image, ImageOps

import config

logger = logging.getLogger(__name__)

# Security: Max dimension and decompress bomb safety
Image.MAX_IMAGE_PIXELS = 40_000_000

class ImageEditEngine:
    def __init__(self):
        self.local_url = getattr(config, "SD_LOCAL_URL", "http://127.0.0.1:7860")
        storage_base = getattr(config, "STORAGE_DIR", Path(config.BASE_DIR) / "storage")
        self.save_dir = storage_base / "images" / "edited"
        self.upload_dir = storage_base / "images" / "uploaded"
        self.save_dir.mkdir(parents=True, exist_ok=True)
        self.upload_dir.mkdir(parents=True, exist_ok=True)

    def _ensure_forge_running(self) -> bool:
        """Checks if Forge API is responding; if not, launches it in the background."""
        import subprocess
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

    def save_uploaded_image(self, file_bytes: bytes, filename: str) -> Tuple[str, str, int, int]:
        """
        Validates, strips unsafe EXIF, converts to standard sRGB, saves to disk,
        and returns (filepath, base64_str, width, height).
        """
        # Strict validation on upload byte size (max 25MB)
        if len(file_bytes) > 25 * 1024 * 1024:
            raise ValueError("Upload exceeds maximum allowed size (25MB).")

        try:
            image = Image.open(io.BytesIO(file_bytes))
            # Format validation
            if (image.format or "").upper() not in ("PNG", "JPEG", "JPG", "WEBP"):
                raise ValueError(f"Unsupported image format: {image.format}. Only PNG, JPEG, WEBP are accepted.")
            # Auto-orient EXIF metadata if present
            image = ImageOps.exif_transpose(image)
        except Exception as e:
            if isinstance(e, ValueError):
                raise
            raise ValueError(f"Corrupted or invalid image payload: {e}")

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
        Executes img2img, localized inpainting, or ControlNet IP2P instruction edit via SD-Forge.
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

        # Check if model requested is a ControlNet model
        controlnet_unit = None
        if model_checkpoint and "controlnet:" in model_checkpoint:
            cn_model_name = model_checkpoint.replace("controlnet:", "")
            # Determine appropriate module
            if "ip2p" in cn_model_name.lower():
                cn_module = "none"
            elif "inpaint" in cn_model_name.lower():
                cn_module = "inpaint_only"
            elif "openpose" in cn_model_name.lower():
                cn_module = "openpose_full"
            else:
                cn_module = "none"

            controlnet_unit = {
                "enabled": True,
                "module": cn_module,
                "model": cn_model_name,
                "weight": 1.0,
                "resize_mode": "Just Resize",
                "control_mode": "Balanced",
            }
            payload["alwayson_scripts"] = {
                "controlnet": {
                    "args": [controlnet_unit]
                }
            }
        elif model_checkpoint:
            actual_cp = model_checkpoint.replace("local:", "")
            try:
                requests.post(
                    f"{self.local_url}/sdapi/v1/options",
                    json={"sd_model_checkpoint": actual_cp},
                    timeout=30
                )
            except Exception as e:
                logger.warning(f"Failed to switch model checkpoint for img2img: {e}")

        if clean_mask:
            payload["mask"] = clean_mask
            payload["inpainting_fill"] = 1 # original
            payload["inpaint_full_res"] = True
            payload["inpaint_full_res_padding"] = 32

        headers = {"Content-Type": "application/json"}
        try:
            self._ensure_forge_running()
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

    def upscale_image(
        self,
        image_b64: str,
        upscaler_name: str = "R-ESRGAN 4x+",
        upscaling_resize: float = 2.0
    ) -> Optional[bytes]:
        """
        Upscales an image using SD Forge's local hardware-accelerated upscalers
        (R-ESRGAN 4x+, SwinIR 4x, DAT x2, etc.) without cloud APIs.
        """
        if "base64," in image_b64:
            image_b64 = image_b64.split("base64,")[1]

        payload = {
            "image": image_b64,
            "upscaler_1": upscaler_name,
            "upscaling_resize": float(upscaling_resize)
        }
        try:
            self._ensure_forge_running()
            res = requests.post(
                f"{self.local_url}/sdapi/v1/extra-single-image",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=120
            )
            if res.status_code == 200:
                data = res.json()
                image_out = data.get("image")
                if image_out:
                    return base64.b64decode(image_out)
            logger.error(f"SD Forge upscale failed with status {res.status_code}: {res.text[:200]}")
            return None
        except Exception as e:
            logger.error(f"SD Forge upscale exception: {e}")
            return None

    def segment_image(
        self,
        image_b64: str,
        module: str = "seg_ofade20k",
        resolution: int = 512
    ) -> Optional[bytes]:
        """
        Runs neural object/scene semantic segmentation using Forge's local ControlNet preprocessors
        (e.g., 'seg_ofade20k', 'seg_ufade20k', 'seg_ofcoco', 'seg_anime_face').
        Returns the segmented mask bitmap as bytes.
        """
        if "base64," in image_b64:
            image_b64 = image_b64.split("base64,")[1]

        payload = {
            "controlnet_module": module,
            "controlnet_input_images": [image_b64],
            "controlnet_processor_res": resolution,
            "controlnet_threshold_a": 64,
            "controlnet_threshold_b": 64
        }
        try:
            self._ensure_forge_running()
            res = requests.post(
                f"{self.local_url}/controlnet/detect",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=60
            )
            if res.status_code == 200:
                data = res.json()
                images = data.get("images", [])
                if images:
                    return base64.b64decode(images[0])
            logger.error(f"ControlNet segment failed with status {res.status_code}: {res.text[:200]}")
            return None
        except Exception as e:
            logger.error(f"ControlNet segment exception: {e}")
            return None
