"""
modules/wake_word.py — JARVIS Wake Word & Barge-In Detector (OpenWakeWord)
==========================================================================
Listens continuously on a background daemon thread for:
1. "Hey JARVIS" wake-word via OpenWakeWord (when idle or speaking).
2. Voice Barge-In via VAD / energy during TTS playback (instant interruption).

If JARVIS is currently speaking:
  - If a wake word is detected, it triggers on_interrupt() to immediately
    silence TTS and switch straight to listening for the new command.
  - If voice activity exceeds barge-in threshold for multiple consecutive
    chunks during playback, it signals interruption as well.
"""

import logging
import threading
import time
from typing import Callable, Optional

import numpy as np
import sounddevice as sd
import openwakeword
from openwakeword.model import Model
from openwakeword.vad import VAD

import config

logger = logging.getLogger(__name__)

# Pre-download models if missing
try:
    openwakeword.utils.download_models()
except Exception as _exc:
    logger.warning(
        f"OpenWakeWord model download failed (offline?): {_exc}."
    )


class WakeWordDetector:
    """
    Continuous background listener for wake-word and voice barge-in.

    Streams audio from the microphone in a daemon thread.
    - When idle: triggers `callback()` when wake word is detected.
    - When JARVIS is speaking (`tts.is_speaking`):
        triggers `on_interrupt()` to immediately stop TTS playback
        and activate listener without requiring pause/resume locks.
    """

    def __init__(
        self,
        callback: Callable[[], None],
        on_interrupt: Optional[Callable[[], None]] = None,
        tts_engine=None,
    ) -> None:
        self._callback = callback
        self._on_interrupt = on_interrupt
        self._tts = tts_engine

        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._pause_event = threading.Event()  # Manual pause if ever needed
        self._pause_event.clear()

        # VAD model for voice barge-in detection
        try:
            self._vad = VAD()
        except Exception as e:
            logger.warning(f"Could not initialize standalone VAD: {e}")
            self._vad = None

        logger.info("Initializing OpenWakeWord model for 'hey_jarvis'...")
        self._model = Model(
            wakeword_models=["hey_jarvis"],
            inference_framework="onnx",
            vad_threshold=0.3,
        )
        logger.info("Wake word detector initialized with barge-in support.")

    def set_interrupt_callback(self, fn: Callable[[], None]) -> None:
        self._on_interrupt = fn

    def set_tts(self, tts_engine) -> None:
        self._tts = tts_engine

    def start(self) -> None:
        if self._running:
            logger.warning("WakeWordDetector.start() called but already running.")
            return

        self._running = True
        self._thread = threading.Thread(
            target=self._listen_loop,
            daemon=True,
            name="WakeWord-Listener",
        )
        self._thread.start()
        logger.info("Wake word & barge-in listener started on background thread.")

    def stop(self) -> None:
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3.0)
            logger.info("Wake word listener stopped.")

    def pause(self) -> None:
        """Pause wake word callbacks explicitly."""
        self._pause_event.set()

    def resume(self) -> None:
        """Resume wake word callbacks explicitly."""
        self._pause_event.clear()
        self._model.reset()

    def is_running(self) -> bool:
        return self._running and (self._thread is not None) and self._thread.is_alive()

    def _listen_loop(self) -> None:
        sample_rate = config.SAMPLE_RATE
        chunk_samples = int(sample_rate * config.CHUNK_DURATION_MS / 1000)
        threshold = config.WAKE_WORD_THRESHOLD
        cooldown_chunks = int(1.5 * 1000 / config.CHUNK_DURATION_MS)
        chunks_since_last_detection = cooldown_chunks

        # Barge-in tracking during TTS
        speech_chunks_during_tts = 0
        REQUIRED_BARGEIN_CHUNKS = 5  # ~150ms of sustained speech

        try:
            with sd.InputStream(
                samplerate=sample_rate,
                channels=1,
                dtype="int16",
                blocksize=chunk_samples,
                device=config.INPUT_DEVICE_INDEX,
            ) as stream:
                while self._running:
                    chunk, overflowed = stream.read(chunk_samples)
                    if overflowed:
                        logger.debug("Wake word stream overflow.")

                    audio_int16 = chunk[:, 0]
                    chunks_since_last_detection += 1

                    # Check if JARVIS is currently speaking
                    is_jarvis_speaking = bool(self._tts and getattr(self._tts, "is_speaking", False))

                    # 1. Run OpenWakeWord prediction
                    self._model.predict(audio_int16)
                    scores = self._model.prediction_buffer.get("hey_jarvis", [])
                    latest_score = float(scores[-1]) if scores else 0.0

                    # 2. Check for Wake Word trigger
                    if (
                        latest_score >= threshold
                        and chunks_since_last_detection >= cooldown_chunks
                        and not self._pause_event.is_set()
                    ):
                        logger.info(f"Wake word detected! Score: {latest_score:.3f} (Speaking: {is_jarvis_speaking})")
                        chunks_since_last_detection = 0
                        self._model.reset()

                        if is_jarvis_speaking and self._on_interrupt:
                            # Direct voice interruption of active speech
                            try:
                                self._on_interrupt()
                            except Exception as exc:
                                logger.error(f"Interruption callback error: {exc}")
                        else:
                            try:
                                self._callback()
                            except Exception as exc:
                                logger.error(f"Wake word callback error: {exc}")
                        continue

                    # 3. Voice Barge-In detection during TTS (if user speaks over JARVIS)
                    if is_jarvis_speaking and self._on_interrupt:
                        vad_score = 0.0
                        if self._vad:
                            try:
                                vad_score = float(self._vad.predict(audio_int16))
                            except Exception:
                                vad_score = 0.0
                        else:
                            # RMS fallback
                            rms = float(np.sqrt(np.mean((audio_int16.astype(np.float32) / 32768.0) ** 2)))
                            vad_score = 1.0 if rms > (config.SILENCE_THRESHOLD * 2.0) else 0.0

                        if vad_score >= 0.75:
                            speech_chunks_during_tts += 1
                            if speech_chunks_during_tts >= REQUIRED_BARGEIN_CHUNKS:
                                logger.info(f"Voice barge-in triggered during TTS playback! (VAD: {vad_score:.2f})")
                                speech_chunks_during_tts = 0
                                try:
                                    self._on_interrupt()
                                except Exception as exc:
                                    logger.error(f"Interruption callback error: {exc}")
                        else:
                            speech_chunks_during_tts = max(0, speech_chunks_during_tts - 1)
                    else:
                        speech_chunks_during_tts = 0

        except Exception as exc:
            logger.error(f"Wake word listen loop crashed: {exc}", exc_info=True)
            self._running = False
