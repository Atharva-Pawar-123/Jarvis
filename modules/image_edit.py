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

    def remove_background(
        self,
        image_b64: str,
        threshold: int = 240
    ) -> Optional[bytes]:
        """
        Generates an isolated subject with transparent background (PNG).
        Uses color/luminance mask analysis with PIL to cleanly isolate subjects.
        """
        if "base64," in image_b64:
            image_b64 = image_b64.split("base64,")[1]

        try:
            raw_bytes = base64.b64decode(image_b64)
            img = Image.open(io.BytesIO(raw_bytes)).convert("RGBA")
            datas = img.getdata()

            new_data = []
            for item in datas:
                # Detect near-white or uniform background boundaries
                if item[0] > threshold and item[1] > threshold and item[2] > threshold:
                    new_data.append((255, 255, 255, 0))
                else:
                    new_data.append(item)

            img.putdata(new_data)
            out_buf = io.BytesIO()
            img.save(out_buf, format="PNG")
            return out_buf.getvalue()
        except Exception as e:
            logger.error(f"Background removal failed: {e}")
            return None

    def replace_background(
        self,
        image_b64: str,
        prompt: str,
        negative_prompt: str = "",
        denoising_strength: float = 0.85,
        steps: int = 25,
        cfg_scale: float = 7.0,
        threshold: int = 240
    ) -> Optional[bytes]:
        """
        Replaces the background of an image while preserving the subject.
        1. Detects background (near-white pixels) → creates binary mask
        2. Inverts mask so background = white (inpaint region), subject = black (preserve)
        3. Runs SD Forge inpainting with the user's prompt for the new background
        """
        if "base64," in image_b64:
            image_b64 = image_b64.split("base64,")[1]

        try:
            raw_bytes = base64.b64decode(image_b64)
            img = Image.open(io.BytesIO(raw_bytes)).convert("RGB")
            w, h = img.size

            # Build mask: white = area to repaint (background), black = preserve (subject)
            mask = Image.new("L", (w, h), 0)
            pixels = img.getdata()
            mask_data = []
            for px in pixels:
                if px[0] > threshold and px[1] > threshold and px[2] > threshold:
                    mask_data.append(255)  # Background → repaint
                else:
                    mask_data.append(0)    # Subject → preserve
            mask.putdata(mask_data)

            # Encode mask to base64
            mask_buf = io.BytesIO()
            mask.save(mask_buf, format="PNG")
            mask_b64 = base64.b64encode(mask_buf.getvalue()).decode("utf-8")

            # Run inpainting via edit_image with the generated mask
            return self.edit_image(
                init_image_b64=image_b64,
                prompt=prompt,
                mask_b64=mask_b64,
                negative_prompt=negative_prompt or "blurry, low quality, artifacts, text, watermark",
                denoising_strength=denoising_strength,
                steps=steps,
                cfg_scale=cfg_scale,
                sampler_name="Euler a"
            )
        except Exception as e:
            logger.error(f"Background replacement failed: {e}")
            return None

    def outpaint_image(
        self,
        image_b64: str,
        prompt: str,
        target_ratio: str = "16:9",
        negative_prompt: str = "",
        denoising_strength: float = 0.90,
        steps: int = 25,
        cfg_scale: float = 7.0
    ) -> Optional[bytes]:
        """
        Expands an image to a new aspect ratio via outpainting (generative fill).
        Pads the original image onto a larger canvas, creates a mask over the
        empty (expanded) regions, and runs SD Forge inpainting to fill them.
        """
        if "base64," in image_b64:
            image_b64 = image_b64.split("base64,")[1]

        RATIOS = {
            "16:9": (16, 9),
            "9:16": (9, 16),
            "4:3": (4, 3),
            "3:4": (3, 4),
            "21:9": (21, 9),
            "1:1": (1, 1),
        }
        ratio = RATIOS.get(target_ratio, (16, 9))

        try:
            raw_bytes = base64.b64decode(image_b64)
            img = Image.open(io.BytesIO(raw_bytes)).convert("RGB")
            orig_w, orig_h = img.size

            # Calculate new canvas size preserving max original dimension
            rw, rh = ratio
            # Fit the original image inside the target ratio canvas
            if orig_w / orig_h > rw / rh:
                # Original is wider than target → expand height
                new_w = orig_w
                new_h = int(orig_w * rh / rw)
            else:
                # Original is taller than target → expand width
                new_h = orig_h
                new_w = int(orig_h * rw / rh)

            # Ensure divisible by 64 for SD compatibility
            new_w = max(384, min(1024, (new_w // 64) * 64))
            new_h = max(384, min(1024, (new_h // 64) * 64))

            # If canvas is same or smaller, nothing to outpaint
            if new_w <= orig_w and new_h <= orig_h:
                logger.info("Image already matches target aspect ratio, no outpainting needed.")
                return None

            # Center the original image on the new canvas
            canvas = Image.new("RGB", (new_w, new_h), (128, 128, 128))
            paste_x = (new_w - orig_w) // 2
            paste_y = (new_h - orig_h) // 2
            # Resize original if it exceeds canvas
            if orig_w > new_w or orig_h > new_h:
                img.thumbnail((new_w, new_h), Image.Resampling.LANCZOS)
                paste_x = (new_w - img.width) // 2
                paste_y = (new_h - img.height) // 2
            canvas.paste(img, (paste_x, paste_y))

            # Create mask: white = expanded region (generate), black = original image (preserve)
            mask = Image.new("L", (new_w, new_h), 255)  # All white
            # Black out the original image region
            orig_region = Image.new("L", (img.width, img.height), 0)
            mask.paste(orig_region, (paste_x, paste_y))

            # Encode canvas and mask
            canvas_buf = io.BytesIO()
            canvas.save(canvas_buf, format="PNG")
            canvas_b64 = base64.b64encode(canvas_buf.getvalue()).decode("utf-8")

            mask_buf = io.BytesIO()
            mask.save(mask_buf, format="PNG")
            mask_b64 = base64.b64encode(mask_buf.getvalue()).decode("utf-8")

            # Run inpainting on the expanded canvas
            return self.edit_image(
                init_image_b64=canvas_b64,
                prompt=prompt or "seamless natural extension of the scene, same style and lighting",
                mask_b64=mask_b64,
                negative_prompt=negative_prompt or "seams, artifacts, blurry, mismatched colors, text",
                denoising_strength=denoising_strength,
                steps=steps,
                cfg_scale=cfg_scale,
                sampler_name="Euler a"
            )
        except Exception as e:
            logger.error(f"Outpainting failed: {e}")
            return None
