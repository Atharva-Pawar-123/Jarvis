"""
modules/voice_auth.py — JARVIS Voice Authentication
===================================================
Uses SpeechBrain's ECAPA-TDNN model to verify the user's identity.
Requires an initial "enrollment" recording to establish a baseline.
"""

import logging
from pathlib import Path
from typing import Optional

import torch
from speechbrain.inference.speaker import SpeakerRecognition

logger = logging.getLogger(__name__)


class VoiceAuthenticator:
    """
    Handles speaker verification to protect sensitive commands.
    """

    def __init__(self, model_dir: str = "models/speaker_model", enrollment_dir: str = "data/enrollment") -> None:
        self.model_dir = Path(model_dir)
        self.enrollment_dir = Path(enrollment_dir)
        self.enrollment_dir.mkdir(parents=True, exist_ok=True)
        
        self.gold_path = self.enrollment_dir / "user_gold.wav"
        
        # Load the model (lazy-loaded to save memory)
        self._model: Optional[SpeakerRecognition] = None
        logger.info("Voice Authenticator ready (model loads on first verify).")

    def _ensure_model_loaded(self) -> None:
        if self._model is not None:
            return
        
        logger.info("Loading SpeechBrain speaker recognition model...")
        device = "cuda" if torch.cuda.is_available() else "cpu"
        self._model = SpeakerRecognition.from_hparams(
            source="speechbrain/spkrec-ecapa-voxceleb",
            savedir=str(self.model_dir),
            run_opts={"device": device}
        )
        logger.info(f"Speaker recognition model loaded on {device}.")

    def is_enrolled(self) -> bool:
        """Check if the user has provided a reference voice sample."""
        return self.gold_path.exists()

    def enroll(self, sample_path: str) -> bool:
        """
        Save a reference audio sample as the 'gold' standard.
        """
        try:
            import shutil
            shutil.copy(sample_path, self.gold_path)
            logger.info(f"User enrolled successfully with sample: {sample_path}")
            return True
        except Exception as exc:
            logger.error(f"Enrollment failed: {exc}")
            return False

    def verify(self, test_sample_path: str, threshold: float = 0.25) -> bool:
        """
        Compare a new audio sample against the enrolled gold sample.
        
        Args:
            test_sample_path: Path to the audio to verify.
            threshold: Similarity threshold (model-specific, ECAPA uses ~0.25).
            
        Returns:
            bool: True if speaker matches, False otherwise.
        """
        if not self.is_enrolled():
            logger.warning("Verification attempted without enrollment. Defaulting to True for now.")
            return True

        self._ensure_model_loaded()
        
        try:
            score, prediction = self._model.verify_files(
                str(self.gold_path), 
                str(test_sample_path)
            )
            logger.info(f"Speaker verification score: {score.item():.4f} | Match: {prediction.item()}")
            return bool(prediction.item())
        except Exception as exc:
            logger.error(f"Verification failed: {exc}")
            return False
