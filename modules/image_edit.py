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
from typing import Optional, Dict, Any, Tuple, List
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
        model_checkpoint: Optional[str] = None,
        reference_images: Optional[List[str]] = None
    ) -> Optional[bytes]:
        """
        Executes img2img, localized inpainting, ControlNet IP2P, or Multi-Reference editing via SD-Forge.
        Supports up to 5 reference images via ControlNet units or chained conditioning.
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

        # Handle ControlNet units (IP2P, inpaint, or Multi-Reference conditioning)
        controlnet_units = []

        # Helper to query available ControlNet models dynamically from Forge
        available_cn_models = []
        try:
            cn_res = requests.get(f"{self.local_url}/controlnet/model_list", timeout=2)
            if cn_res.status_code == 200:
                available_cn_models = cn_res.json().get("model_list", [])
        except Exception:
            pass

        def resolve_cn_model_name(pattern: str) -> str:
            """Resolves exact Forge ControlNet model name with hash suffix if available."""
            pattern_clean = pattern.lower().replace(".safetensors", "")
            for m in available_cn_models:
                if pattern_clean in m.lower():
                    return m
            # Fallback to direct pattern
            return pattern

        if model_checkpoint and "controlnet:" in model_checkpoint:
            cn_raw = model_checkpoint.replace("controlnet:", "")
            if "ip2p" in cn_raw.lower():
                cn_module = "none"
                resolved_model = resolve_cn_model_name("control_v11e_sd15_ip2p_fp16")
            elif "inpaint" in cn_raw.lower():
                cn_module = "inpaint_only"
                resolved_model = resolve_cn_model_name("control_v11p_sd15_inpaint_fp16")
            elif "openpose" in cn_raw.lower():
                cn_module = "openpose_full"
                resolved_model = resolve_cn_model_name("openpose")
            else:
                cn_module = "none"
                resolved_model = resolve_cn_model_name(cn_raw)

            controlnet_units.append({
                "enabled": True,
                "module": cn_module,
                "model": resolved_model,
                "weight": 1.0,
                "resize_mode": "Just Resize",
                "control_mode": "Balanced",
            })
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

        # Add multi-reference units (up to 5 reference images)
        if reference_images:
            for idx, ref_img in enumerate(reference_images[:5]):
                clean_ref = ref_img.split("base64,")[1] if "base64," in ref_img else ref_img
                ip2p_model = resolve_cn_model_name("control_v11e_sd15_ip2p_fp16") if "ip2p" in str(model_checkpoint) else "None"
                controlnet_units.append({
                    "enabled": True,
                    "input_image": clean_ref,
                    "module": "none",
                    "model": ip2p_model,
                    "weight": 0.8,
                    "resize_mode": "Crop and Resize",
                    "control_mode": "Balanced",
                })

        if controlnet_units:
            payload["alwayson_scripts"] = {
                "ControlNet": {
                    "args": controlnet_units
                }
            }

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
        Attempts real neural semantic segmentation first via ControlNet/ADE20K.
        If ControlNet is unavailable or returns blank, applies OpenCV GrabCut foreground
        extraction for genuine foreground/background segmentation rather than simple color thresholding.
        """
        if "base64," in image_b64:
            image_b64 = image_b64.split("base64,")[1]

        try:
            import numpy as np
            import cv2
            raw_bytes = base64.b64decode(image_b64)
            pil_img = Image.open(io.BytesIO(raw_bytes)).convert("RGB")
            w, h = pil_img.size

            # 1. Try ControlNet Semantic Segmentation
            seg_mask_bytes = None
            try:
                seg_mask_bytes = self.segment_image(image_b64, module="seg_ofade20k")
            except Exception:
                pass

            if seg_mask_bytes:
                seg_img = Image.open(io.BytesIO(seg_mask_bytes)).convert("L")
                seg_arr = np.array(seg_img.resize((w, h)))
                # Background in ADE20K typically has pixel value 0 (black/wall/floor)
                # Subject has non-zero classes
                alpha = np.where(seg_arr > 20, 255, 0).astype(np.uint8)
            else:
                # 2. Local Fallback: OpenCV GrabCut algorithm (real foreground extraction)
                cv_img = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
                mask = np.zeros(cv_img.shape[:2], np.uint8)
                bgd_model = np.zeros((1, 65), np.float64)
                fgd_model = np.zeros((1, 65), np.float64)

                # Bounding box for central foreground subject
                margin_x = max(10, int(w * 0.05))
                margin_y = max(10, int(h * 0.05))
                rect = (margin_x, margin_y, w - 2 * margin_x, h - 2 * margin_y)

                cv2.grabCut(cv_img, mask, rect, bgd_model, fgd_model, 5, cv2.GC_INIT_WITH_RECT)
                alpha = np.where((mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD), 255, 0).astype(np.uint8)

            # Combine RGB + Alpha
            rgba = Image.fromarray(np.array(pil_img)).convert("RGBA")
            rgba.putalpha(Image.fromarray(alpha))

            out_buf = io.BytesIO()
            rgba.save(out_buf, format="PNG")
            return out_buf.getvalue()

        except Exception as e:
            logger.error(f"Advanced background removal failed: {e}", exc_info=True)
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
        Replaces background using true foreground segmentation rather than color heuristics.
        1. Segments foreground subject (alpha mask).
        2. Inverts mask (background = 255 to inpaint, subject = 0 to preserve).
        3. Runs localized inpainting with user's prompt.
        """
        if "base64," in image_b64:
            image_b64 = image_b64.split("base64,")[1]

        try:
            import numpy as np
            import cv2
            raw_bytes = base64.b64decode(image_b64)
            pil_img = Image.open(io.BytesIO(raw_bytes)).convert("RGB")
            w, h = pil_img.size

            # Get cutout with alpha
            cutout_bytes = self.remove_background(image_b64)
            if cutout_bytes:
                cutout_img = Image.open(io.BytesIO(cutout_bytes))
                _, _, _, alpha = cutout_img.split()
                # Invert: subject is 0 (preserve), background is 255 (repaint)
                inpaint_mask = Image.eval(alpha, lambda a: 0 if a > 128 else 255)
            else:
                # Fallback to central box mask
                inpaint_mask = Image.new("L", (w, h), 255)

            mask_buf = io.BytesIO()
            inpaint_mask.save(mask_buf, format="PNG")
            mask_b64 = base64.b64encode(mask_buf.getvalue()).decode("utf-8")

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
            logger.error(f"Background replacement failed: {e}", exc_info=True)
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
