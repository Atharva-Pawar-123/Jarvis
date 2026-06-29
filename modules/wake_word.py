"""
modules/wake_word.py — JARVIS Wake Word Detection (OpenWakeWord)
================================================================
Listens continuously on a background daemon thread for the "hey_jarvis"
wake word using OpenWakeWord. When detected, invokes a callback function
to signal the main thread. Audio conflicts are avoided by pausing the
detector while JARVIS is speaking (TTS holds a shared speaking_event).
"""

import logging
import threading
from typing import Callable

import sounddevice as sd
import openwakeword
from openwakeword.model import Model

import config

logger = logging.getLogger(__name__)

# Download pre-trained OpenWakeWord models if not already present
openwakeword.utils.download_models()


class WakeWordDetector:
    """
    Background wake word listener using OpenWakeWord.

    Streams audio from the microphone in a daemon thread. When the
    "hey_jarvis" model confidence exceeds WAKE_WORD_THRESHOLD, the
    provided callback is invoked once per wake word event.

    Args:
        callback (callable): Zero-argument function called on wake word detection.
    """

    def __init__(self, callback: Callable[[], None]) -> None:
        """
        Initialize the wake word detector with the specified callback.

        Args:
            callback (callable): Function to call when "hey_jarvis" is detected.
        """
        self._callback = callback
        self._running = False
        self._thread: threading.Thread | None = None
        self._pause_event = threading.Event()  # Set = paused (don't callback)
        self._pause_event.clear()

        logger.info("Initializing OpenWakeWord model for 'hey_jarvis'...")
        self._model = Model(wakeword_models=["hey_jarvis"], inference_framework="onnx")
        logger.info("Wake word detector initialized.")

    def start(self) -> None:
        """
        Start the background listening thread.

        The thread runs as a daemon so it automatically exits when the
        main program terminates. Does nothing if already running.
        """
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
        logger.info("Wake word listener started on background thread.")

    def stop(self) -> None:
        """
        Stop the background listening thread cleanly.

        Sets the running flag to False and waits up to 3 seconds for
        the thread to finish.
        """
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3.0)
            logger.info("Wake word listener stopped.")

    def pause(self) -> None:
        """
        Pause wake word callbacks (e.g., while JARVIS is speaking).

        Detection still runs internally, but the callback will not be
        invoked while paused. This prevents JARVIS from hearing itself.
        """
        self._pause_event.set()

    def resume(self) -> None:
        """
        Resume wake word callbacks after a pause.
        """
        self._pause_event.clear()
        self._model.reset()  # Reset model state to avoid stale detections

    def is_running(self) -> bool:
        """
        Return whether the wake word detector is currently active.

        Returns:
            bool: True if the background thread is running.
        """
        return self._running and (self._thread is not None) and self._thread.is_alive()

    def _listen_loop(self) -> None:
        """
        Internal: continuous audio streaming loop running on the background thread.

        Reads audio in chunks of CHUNK_DURATION_MS milliseconds. Runs each
        chunk through the OpenWakeWord model. Invokes the callback once a
        wake word event is confirmed (score > threshold), then resets model
        state to prevent repeated triggers from a single utterance.
        """
        sample_rate = config.SAMPLE_RATE
        chunk_samples = int(sample_rate * config.CHUNK_DURATION_MS / 1000)
        threshold = config.WAKE_WORD_THRESHOLD
        cooldown_chunks = int(2.0 * 1000 / config.CHUNK_DURATION_MS)  # 2s cooldown
        chunks_since_last_detection = cooldown_chunks  # start ready

        logger.debug(
            f"Wake word loop: chunk_samples={chunk_samples}, threshold={threshold}"
        )

        try:
            with sd.InputStream(
                samplerate=sample_rate,
                channels=1,
                dtype="int16",
                blocksize=chunk_samples,
                device=config.INPUT_DEVICE_INDEX
            ) as stream:
                while self._running:
                    chunk, overflowed = stream.read(chunk_samples)
                    if overflowed:
                        logger.debug("Wake word stream overflow.")

                    audio_int16 = chunk[:, 0]
                    chunks_since_last_detection += 1

                    self._model.predict(audio_int16)
                    scores = self._model.prediction_buffer.get("hey_jarvis", [])
                    latest_score = float(scores[-1]) if scores else 0.0

                    if (
                        latest_score >= threshold
                        and chunks_since_last_detection >= cooldown_chunks
                        and not self._pause_event.is_set()
                    ):
                        logger.info(
                            f"Wake word detected! Score: {latest_score:.3f}"
                        )
                        chunks_since_last_detection = 0
                        self._model.reset()
                        try:
                            self._callback()
                        except Exception as exc:
                            logger.error(
                                f"Wake word callback raised an exception: {exc}",
                                exc_info=True,
                            )

        except Exception as exc:
            logger.error(f"Wake word listen loop crashed: {exc}", exc_info=True)
            self._running = False
