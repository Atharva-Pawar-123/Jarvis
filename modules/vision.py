"""
modules/vision.py — JARVIS Vision Engine (Moondream2)
======================================================
Provides screen description and visual question answering (VQA) using
the Moondream2 multimodal model. The model is lazy-loaded on first use
to avoid consuming GPU VRAM at startup. Supports screen capture (mss)
and webcam capture (OpenCV).
"""

import logging
from typing import Optional

import torch
from PIL import Image

import config

logger = logging.getLogger(__name__)


class VisionEngine:
    """
    Computer vision engine powered by Moondream2.

    The model is NOT loaded at init time — it is loaded on the first
    vision request to conserve GPU memory. Screen capture uses mss;
    webcam capture uses OpenCV.
    """

    def __init__(self) -> None:
        """
        Initialize the vision engine in lazy-load mode.

        The Moondream2 model is not loaded until the first vision call.
        """
        self._model = None
        self._tokenizer = None
        
        # Sprint 6 Additions
        try:
            from modules.mood_detector import MoodDetector
            self.mood_detector = MoodDetector()
        except Exception as exc:
            logger.warning(f"Failed to load MoodDetector: {exc}")
            self.mood_detector = None
            
        logger.info("Vision engine ready (model loads on first use).")

    def _ensure_loaded(self) -> None:
        """
        Load the Moondream2 model and tokenizer if not already loaded.

        Selects CUDA if available, otherwise CPU. Logs when loading begins
        and completes so the user knows to wait.
        """
        if self._model is not None:
            return

        from transformers import AutoModelForCausalLM, AutoTokenizer, AutoConfig, PreTrainedModel

        # --- Compatibility patch for older Moondream2 revision on newer Transformers ---
        if not hasattr(PreTrainedModel, 'all_tied_weights_keys'):
            def _get_all_tied_weights_keys(self):
                return getattr(self, '_tied_weights_keys', None) or {}
            def _set_all_tied_weights_keys(self, value):
                self._tied_weights_keys = value
            PreTrainedModel.all_tied_weights_keys = property(_get_all_tied_weights_keys, _set_all_tied_weights_keys)
        # -------------------------------------------------------------------------------

        device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(
            f"Loading Moondream2 model '{config.VISION_MODEL}' "
            f"on {device} (revision={config.VISION_REVISION})..."
        )

        self._tokenizer = AutoTokenizer.from_pretrained(
            config.VISION_MODEL,
            revision=config.VISION_REVISION,
            trust_remote_code=True,
        )

        # --- Config patching to bypass pad_token_id and rope_scaling missing errors ---
        model_config = AutoConfig.from_pretrained(
            config.VISION_MODEL,
            revision=config.VISION_REVISION,
            trust_remote_code=True,
        )
        if hasattr(model_config, 'text_config'):
            model_config.text_config.pad_token_id = self._tokenizer.eos_token_id
            if hasattr(model_config.text_config, 'rope_scaling'):
                model_config.text_config.rope_scaling = None
        # ------------------------------------------------------------------------------

        self._model = AutoModelForCausalLM.from_pretrained(
            config.VISION_MODEL,
            revision=config.VISION_REVISION,
            trust_remote_code=True,
            config=model_config,
            device_map=device,
        )
        self._model.eval()
        logger.info(f"Moondream2 loaded on {device} and ready.")

    def capture_screen(self) -> Image.Image:
        """
        Capture the primary monitor and return it as a PIL Image.

        Returns:
            PIL.Image.Image: Screenshot of the configured monitor.
        """
        import mss

        with mss.mss() as sct:
            monitor = sct.monitors[config.SCREEN_CAPTURE_MONITOR]
            raw = sct.grab(monitor)
            img = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
        logger.debug(f"Screen captured: {img.size}")
        return img

    def capture_webcam(self) -> Optional[Image.Image]:
        """
        Capture a single frame from the default webcam using OpenCV.

        Returns:
            PIL.Image.Image: Webcam frame as a PIL Image, or None if no
            webcam is found or the capture fails.
        """
        import cv2

        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            logger.warning("No webcam found at index 0.")
            return None

        ret, frame = cap.read()
        cap.release()

        if not ret or frame is None:
            logger.warning("Webcam capture returned no frame.")
            return None

        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(frame_rgb)
        logger.debug(f"Webcam frame captured: {img.size}")
        return img

    def _resize_image(self, image: Image.Image, max_dim: int = 1024) -> Image.Image:
        """
        Resizes the PIL Image if any dimension exceeds max_dim, keeping the aspect ratio.
        """
        # Strip alpha channels to reduce tensor overhead
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
            
        logger.info(f"Resizing and compressing captured image from {w}x{h} to {new_w}x{new_h} for visual model optimization.")
        resample_method = getattr(Image, "Resampling", Image).LANCZOS
        image = image.resize((new_w, new_h), resample_method)
            
        return image

    def describe_image(self, image: Image.Image) -> str:
        """
        Generate a natural language description of a given image.

        Args:
            image (PIL.Image.Image): The image to describe.

        Returns:
            str: A sentence or two describing what is in the image.
        """
        self._ensure_loaded()
        try:
            image = self._resize_image(image)
            enc_image = self._model.encode_image(image)
            description = self._model.answer_question(
                enc_image,
                "Describe what you see in this image in 2-3 concise sentences.",
                self._tokenizer,
            )
            logger.debug(f"Image description: {description[:100]}")
            return description.strip()
        except Exception as exc:
            logger.error(f"Image description failed: {exc}", exc_info=True)
            return "I was unable to analyze the image, sir."

    def answer_about_image(self, image: Image.Image, question: str) -> str:
        """
        Answer a question about a given image using visual question answering.

        Args:
            image (PIL.Image.Image): The image to query.
            question (str): A natural language question about the image.

        Returns:
            str: The model's answer to the question about the image.
        """
        self._ensure_loaded()
        try:
            image = self._resize_image(image)
            enc_image = self._model.encode_image(image)
            answer = self._model.answer_question(
                enc_image,
                question,
                self._tokenizer,
            )
            logger.debug(f"VQA answer: {answer[:100]}")
            return answer.strip()
        except Exception as exc:
            logger.error(f"VQA failed: {exc}", exc_info=True)
            return "I was unable to answer the question about the image, sir."

    def describe_screen(self) -> str:
        """
        Capture the screen and return a description of what is on it.

        Returns:
            str: Natural language description of the screen contents.
        """
        image = self.capture_screen()
        return self.describe_image(image)

    def answer_about_screen(self, question: str) -> str:
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

