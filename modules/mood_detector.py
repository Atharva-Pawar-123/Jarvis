"""
modules/mood_detector.py — JARVIS Mood & Emotion Detection
=============================================================
Uses DeepFace to analyze facial expressions from webcam frames.
Designed to be fault-tolerant: if DeepFace or its dependencies 
(TensorFlow, Keras) are missing, it falls back gracefully.
"""

import logging
import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

class MoodDetector:
    """
    Analyzes webcam frames for human emotion/mood using DeepFace.
    """
    
    def __init__(self):
        self._is_available = False
        try:
            import deepface
            self._is_available = True
            logger.info("MoodDetector ready (DeepFace available).")
        except (ImportError, Exception) as exc:
            logger.warning(f"DeepFace not available ({exc}). Mood detection will be offline.")
            
    def is_available(self) -> bool:
        return self._is_available
        
    def detect_emotion(self, image: Image.Image) -> str:
        """
        Detect the dominant emotion in the provided PIL Image.
        
        Args:
            image (PIL.Image.Image): The webcam frame.
            
        Returns:
            str: The dominant emotion (e.g., 'happy', 'sad', 'angry') or an error message.
        """
        if not self._is_available:
            return "offline (DeepFace library is missing)"
            
        try:
            from deepface import DeepFace
            # Convert PIL Image to OpenCV numpy array format (BGR) for DeepFace
            img_arr = np.array(image)
            # PIL is RGB, DeepFace expects BGR if passing numpy arrays usually, 
            # though it handles RGB numpy arrays if we tell it. Let's convert:
            import cv2
            img_cv = cv2.cvtColor(img_arr, cv2.COLOR_RGB2BGR)
            
            # enforce_detection=False prevents crash if no face is found
            results = DeepFace.analyze(
                img_path=img_cv,
                actions=['emotion'],
                enforce_detection=False,
                silent=True
            )
            
            if isinstance(results, list) and len(results) > 0:
                dominant_emotion = results[0].get('dominant_emotion', 'unknown')
                return dominant_emotion
            return "unknown"
            
        except Exception as exc:
            logger.error(f"Mood detection failed: {exc}")
            return f"error: {exc}"
