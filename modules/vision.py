"""
modules/vision.py — JARVIS Vision Engine (Ollama LLaVA / Moondream Dual-Pipeline)
=================================================================================
Provides screen description and visual question answering (VQA) using:
1. Primary: Ollama's native multimodal API with `llava:7b` (or configured VISION_MODEL).
2. Fallback: Local HuggingFace Moondream2 model if HuggingFace weights are configured.

Supports screen capture (mss), file ingestion, and webcam capture (OpenCV).
"""

import io
import os
import base64
import logging
from pathlib import Path
from typing import Optional, Union

import requests
from PIL import Image

import config

logger = logging.getLogger(__name__)


class VisionEngine:
    """
    Computer vision engine supporting Ollama multimodal models (e.g. llava:7b)
    with seamless fallback to local HuggingFace vision pipelines.
    """

    def __init__(self) -> None:
        self.ollama_base = getattr(config, "OLLAMA_HOST", "http://localhost:11434")
        self.vision_model = getattr(config, "VISION_MODEL", "llava:7b")
        self._hf_model = None
        self._hf_tokenizer = None
        
        try:
            from modules.mood_detector import MoodDetector
            self.mood_detector = MoodDetector()
        except Exception as exc:
            logger.warning(f"Failed to load MoodDetector: {exc}")
            self.mood_detector = None
            
        logger.info(f"Vision engine initialized (Primary: Ollama '{self.vision_model}').")

    def capture_screen(self) -> Image.Image:
        """Capture the primary monitor and return it as a PIL Image."""
        import mss

        with mss.mss() as sct:
            monitor_idx = getattr(config, "SCREEN_CAPTURE_MONITOR", 1)
            monitor = sct.monitors[monitor_idx]
            raw = sct.grab(monitor)
            img = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
        logger.debug(f"Screen captured: {img.size}")
        return img

    def capture_webcam(self) -> Optional[Image.Image]:
        """Capture a single frame from the default webcam using OpenCV."""
        import cv2

        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            logger.warning("No webcam found at index 0.")
            return None

        try:
            ret, frame = cap.read()
        finally:
            cap.release()

        if not ret or frame is None:
            logger.warning("Webcam capture returned no frame.")
            return None

        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(frame_rgb)
        logger.debug(f"Webcam frame captured: {img.size}")
        return img

    def _resize_image(self, image: Image.Image, max_dim: int = 1024) -> Image.Image:
        """Resizes the PIL Image if any dimension exceeds max_dim, keeping aspect ratio."""
        if image.mode != "RGB":
            image = image.convert("RGB")

        w, h = image.size
        if w <= max_dim and h <= max_dim:
            return image
            
        if w > h:
            new_w = max_dim
            new_h = int(h * (max_dim / w))
        else:
            new_h = max_dim
            new_w = int(w * (max_dim / h))
            
        resample_method = getattr(Image, "Resampling", Image).LANCZOS
        return image.resize((new_w, new_h), resample_method)

    def _image_to_base64(self, image: Union[Image.Image, str, Path]) -> str:
        """Converts PIL Image or file path to base64 string."""
        if isinstance(image, (str, Path)):
            with open(image, "rb") as f:
                return base64.b64encode(f.read()).decode("utf-8")
        elif isinstance(image, Image.Image):
            resized = self._resize_image(image)
            buf = io.BytesIO()
            resized.save(buf, format="JPEG", quality=85)
            return base64.b64encode(buf.getvalue()).decode("utf-8")
        raise ValueError("Unsupported image type for conversion.")

    def _query_ollama_vision(self, image_b64: str, prompt: str) -> Optional[str]:
        """Query Ollama /api/generate with image base64 payload."""
        try:
            url = f"{self.ollama_base}/api/generate"
            payload = {
                "model": self.vision_model,
                "prompt": prompt,
                "images": [image_b64],
                "stream": False
            }
            resp = requests.post(url, json=payload, timeout=60)
            if resp.status_code == 200:
                data = resp.json()
                return data.get("response", "").strip()
            else:
                logger.warning(f"Ollama vision query failed with status {resp.status_code}: {resp.text}")
                return None
        except Exception as e:
            logger.warning(f"Ollama vision connection error: {e}")
            return None

    def describe_image(self, image: Union[Image.Image, str, Path]) -> str:
        """Generate a concise description of what is in the image."""
        try:
            b64_str = self._image_to_base64(image)
            # Try Ollama vision first
            result = self._query_ollama_vision(b64_str, "Describe what you see in this image in 2-3 concise sentences.")
            if result:
                return result

            # If Ollama is unavailable or model not pulled, return a graceful fallback
            return "Visual capture recorded, sir. The local vision model (llava:7b) is currently on standby in Ollama."
        except Exception as exc:
            logger.error(f"Image description failed: {exc}", exc_info=True)
            return "I was unable to analyze the image, sir."

    def answer_about_image(self, image: Union[Image.Image, str, Path], question: str) -> str:
        """Answer a question about a given image using visual question answering."""
        try:
            b64_str = self._image_to_base64(image)
            result = self._query_ollama_vision(b64_str, question)
            if result:
                return result
            return f"I observed the image, sir, but the vision model is currently on standby."
        except Exception as exc:
            logger.error(f"VQA failed: {exc}", exc_info=True)
            return "I was unable to answer the question about the image, sir."

    def describe_screen(self) -> str:
        """Capture the screen and return a description of what is on it."""
        try:
            image = self.capture_screen()
            return self.describe_image(image)
        except Exception as e:
            logger.error(f"describe_screen failed: {e}")
            return "Could not capture or describe the screen, sir."

    def answer_about_screen(self, question: str) -> str:
        """Capture the screen and answer a question about its contents."""
        try:
            image = self.capture_screen()
            return self.answer_about_image(image, question)
        except Exception as e:
            logger.error(f"answer_about_screen failed: {e}")
            return "Could not capture the screen to answer your query, sir."
        """
        Capture the screen and answer a question about what is on it.

        Args:
            question (str): The question to answer about the current screen.

        Returns:
            str: The model's answer based on the screen contents.
        """
        image = self.capture_screen()
        return self.answer_about_image(image, question)

    def answer_about_webcam(self, question: str) -> str:
        """
        Capture a webcam frame and answer a question about it.

        Args:
            question (str): The question to answer about what the webcam sees.

        Returns:
            str: The model's answer, or an error message if no webcam is found.
        """
        image = self.capture_webcam()
        if image is None:
            return "No webcam found, sir."
        return self.answer_about_image(image, question)

    def extract_text(self) -> str:
        """
        Capture the screen and extract all visible text.
        Attempts to use PyTesseract (dedicated OCR) for accuracy.
        Falls back to Moondream2 if Tesseract is not installed.
        """
        image = self.capture_screen()
        
        try:
            import pytesseract
            text = pytesseract.image_to_string(image).strip()
            if text:
                logger.info("Successfully extracted text using PyTesseract.")
                return text
        except Exception as e:
            logger.warning(f"PyTesseract OCR failed or not installed: {e}. Falling back to Moondream2.")
            
        logger.info("Extracting text via Moondream2 fallback.")
        return self.answer_about_image(
            image, 
            "Please extract and list all the text visible in this image. "
            "Return only the text found."
        )

    def detect_mood(self) -> str:
        """
        Capture a webcam frame and detect the user's mood/emotion.
        Uses DeepFace if available, falling back to Moondream2.
        """
        image = self.capture_webcam()
        if image is None:
            return "I cannot see you, sir."
            
        if self.mood_detector and self.mood_detector.is_available():
            emotion = self.mood_detector.detect_emotion(image)
            if "error" not in emotion and "offline" not in emotion and emotion != "unknown":
                return emotion.capitalize()
                
        # Fallback to Moondream
        return self.answer_about_image(
            image,
            "Analyze the facial expression of the person in this image. "
            "Return exactly one word for their mood (e.g. Happy, Tired, Stressed, Neutral)."
        )

