"""
modules/tts.py — JARVIS Text-to-Speech (Piper TTS)
====================================================
Synthesizes JARVIS responses to audio using Piper TTS with the deep
male "Alan" voice model. Plays audio via sounddevice. Supports both
blocking and non-blocking (async thread) playback. Strips markdown
formatting before speaking since symbols don't translate to speech.
"""

import logging
import re
import threading
from pathlib import Path
from typing import Optional

import numpy as np
import sounddevice as sd
from piper.voice import PiperVoice

import config

logger = logging.getLogger(__name__)


class TextToSpeech:
    """
    Text-to-speech engine using Piper TTS.

    Loads the configured Piper voice model on initialization. Provides
    blocking and non-blocking speech synthesis with clean audio playback.
    """

    # Regex to strip common markdown symbols that don't make sense in speech
    _MARKDOWN_PATTERN = re.compile(
        r"(\*{1,3}|_{1,3}|`{1,3}|#{1,6}\s?|~~|\[|\]|\(|\)|>|---|\|)"
    )

    def __init__(self) -> None:
        """
        Load the Piper voice model from the configured paths.

        Raises:
            FileNotFoundError: If the .onnx model file does not exist.
        """
        model_path = Path(config.PIPER_MODEL_PATH)
        if not model_path.exists():
            logger.error(f"Piper voice model not found at: {config.PIPER_MODEL_PATH}")
            raise FileNotFoundError(
                f"Piper voice model not found at: {config.PIPER_MODEL_PATH}"
            )

        logger.info(f"Loading Piper TTS model from: {config.PIPER_MODEL_PATH}")
        self._voice = PiperVoice.load(
            model_path=config.PIPER_MODEL_PATH,
            config_path=config.PIPER_CONFIG_PATH,
            use_cuda=False,  # Piper runs on CPU; GPU is reserved for Whisper
        )
        self._lock = threading.Lock()  # Prevent overlapping audio playback
        self.length_scale = 1.0        # Default speaking rate
        logger.info("Piper TTS model loaded and ready.")

    @staticmethod
    def _strip_markdown(text: str) -> str:
        """
        Remove markdown formatting symbols that are not suitable for speech.

        Args:
            text (str): Raw text potentially containing markdown.

        Returns:
            str: Clean text suitable for TTS synthesis.
        """
        cleaned = TextToSpeech._MARKDOWN_PATTERN.sub("", text)
        cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
        return cleaned


    def speak(self, text: str, blocking: bool = True, temp_length_scale: Optional[float] = None) -> None:
        """
        Synthesize and play speech audio for the given text.

        Strips markdown from text before synthesis. Uses sounddevice for
        playback. Thread-safe: only one playback occurs at a time.

        Args:
            text (str): The text for JARVIS to speak. May contain markdown.
            blocking (bool): If True (default), waits for playback to complete
                before returning. If False, plays in a background thread.
            temp_length_scale (float, optional): Temporary speed adjustment for this call.
        """
        if not text or not text.strip():
            return

        clean_text = self._strip_markdown(text)
        if not clean_text.strip():
            return

        effective_length = temp_length_scale if temp_length_scale is not None else self.length_scale

        if blocking:
            self._play_blocking(clean_text, effective_length)
        else:
            thread = threading.Thread(
                target=self._play_blocking,
                args=(clean_text, effective_length),
                daemon=True,
                name="TTS-Playback",
            )
            thread.start()

    def _play_blocking(self, text: str, length_scale: Optional[float] = None) -> None:
        """
        Internal: synthesize text and play it synchronously.

        Acquires the playback lock to prevent audio conflicts.
        Passes length_scale to Piper's SynthesisConfig to control speaking speed.

        Args:
            text (str): Clean text (no markdown) to synthesize and play.
            length_scale (float, optional): Overrides self.length_scale if provided.
        """
        with self._lock:
            try:
                audio_arrays = []
                sample_rate = self._voice.config.sample_rate
                effective_scale = length_scale if length_scale is not None else self.length_scale

                # Try to use Piper's native SynthesisConfig for speed control
                try:
                    from piper.voice import SynthesisConfig
                    synth_config = SynthesisConfig(length_scale=effective_scale)
                    for chunk in self._voice.synthesize(text, synth_config):
                        audio_arrays.append(chunk.audio_float_array)
                        sample_rate = chunk.sample_rate
                except (ImportError, TypeError):
                    # Fallback: synthesize normally and resample for speed
                    for chunk in self._voice.synthesize(text):
                        audio_arrays.append(chunk.audio_float_array)
                        sample_rate = chunk.sample_rate

                if not audio_arrays:
                    return

                audio_array = np.concatenate(audio_arrays, axis=0)

                sd.play(audio_array, samplerate=sample_rate)
                sd.wait()
            except Exception as exc:
                logger.error(f"TTS playback error: {exc}", exc_info=True)

    def speak_async(self, text: str) -> None:
        """
        Non-blocking wrapper: speaks without waiting for completion.

        Args:
            text (str): Text for JARVIS to speak.
        """
        self.speak(text, blocking=False)

    def stop(self) -> None:
        """
        Immediately halts any currently playing audio.
        """
        logger.debug("TTS playback interrupted via stop().")
        sd.stop()

    def increase_speed(self) -> str:
        """
        Increases the speaking rate.
        Returns a confirmation message.
        """
        # Lower length_scale = faster speech
        self.length_scale = max(0.5, self.length_scale * 0.85)
        return "I have increased my speaking rate, sir."

    def decrease_speed(self) -> str:
        """
        Decreases the speaking rate.
        Returns a confirmation message.
        """
        # Higher length_scale = slower speech
        self.length_scale = min(2.0, self.length_scale * 1.15)
        return "I have decreased my speaking rate, sir."

