"""
modules/stt.py — JARVIS Streaming Speech-to-Text (WhisperFlow Architecture)
===========================================================================
Continuous, low-latency speech recognition engine using faster-whisper.
Features:
  - GPU CUDA acceleration with automatic CPU/int8 fallback.
  - Automatic resolution of CUDA / cuBLAS DLL dependencies.
  - Hybrid VAD (Silero VAD + RMS fallback) for instant end-of-speech detection:
    reduces turnaround delay from 1.5s down to ~0.5s.
  - Streaming partial transcription callbacks for live HUD display.
  - Instant cancellation on typed HUD commands or interruption events.
"""

import logging
import os
from pathlib import Path
import threading
import time
from typing import Callable, Optional

import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel

import config

logger = logging.getLogger(__name__)

# Ensure CUDA runtime DLLs (cublas, cudnn) from Forge or local environment are discoverable
def _ensure_cuda_dlls():
    forge_torch_lib = Path(config.BASE_DIR) / "tools" / "forge" / "system" / "python" / "Lib" / "site-packages" / "torch" / "lib"
    if forge_torch_lib.exists():
        try:
            os.add_dll_directory(str(forge_torch_lib))
            os.environ["PATH"] = str(forge_torch_lib) + ";" + os.environ.get("PATH", "")
        except Exception:
            pass

_ensure_cuda_dlls()


class SpeechToText:
    """
    Streaming speech recognition engine.

    Records audio with VAD-guided segmentation. Immediately halts recording
    once sentence termination is detected (silence duration ~0.5-0.6s),
    drastically cutting latency compared to static 1.5s silence waiting.
    """

    def __init__(self) -> None:
        self._device = config.WHISPER_DEVICE
        self._compute_type = config.WHISPER_COMPUTE_TYPE
        self._model = None
        self._init_model()

        # Initialize lightweight Silero VAD from openwakeword cache if available
        self._vad = None
        try:
            from openwakeword.vad import VAD
            self._vad = VAD()
        except Exception:
            logger.debug("Silero VAD not loaded for STT, using RMS silence detector.")

    def _init_model(self):
        """Initialize WhisperModel with CUDA preference and CPU fallback."""
        try:
            logger.info(
                f"Loading Whisper model '{config.WHISPER_MODEL_SIZE}' on "
                f"{self._device} ({self._compute_type})..."
            )
            self._model = WhisperModel(
                config.WHISPER_MODEL_SIZE,
                device=self._device,
                compute_type=self._compute_type,
                cpu_threads=config.WHISPER_THREADS,
                num_workers=1,
            )
            logger.info("Whisper model loaded successfully.")
        except Exception as exc:
            logger.warning(
                f"Failed to load Whisper on {self._device}: {exc}. "
                "Falling back to CPU int8."
            )
            self._device = "cpu"
            self._compute_type = "int8"
            self._model = WhisperModel(
                config.WHISPER_MODEL_SIZE,
                device="cpu",
                compute_type="int8",
                cpu_threads=config.WHISPER_THREADS,
                num_workers=1,
            )
            logger.info("Whisper model loaded on CPU (fallback).")

    def record_until_silence(
        self,
        timeout: Optional[float] = None,
        on_partial_audio: Optional[Callable[[np.ndarray], None]] = None,
    ) -> np.ndarray:
        """
        Record audio from the microphone until user speech ends.

        Uses VAD combined with RMS to catch speech boundaries promptly
        (0.5-0.6s of silence after speech ends recording immediately).
        """
        sample_rate = config.SAMPLE_RATE
        chunk_samples = int(sample_rate * config.CHUNK_DURATION_MS / 1000)
        silence_chunks = int(config.SILENCE_DURATION * 1000 / config.CHUNK_DURATION_MS)
        min_speech_chunks = int(0.3 * 1000 / config.CHUNK_DURATION_MS)

        timeout_chunks = int(timeout * 1000 / config.CHUNK_DURATION_MS) if timeout else None
        max_duration_chunks = int(30.0 * 1000 / config.CHUNK_DURATION_MS)

        audio_buffer = []
        silence_counter = 0
        speech_chunk_count = 0
        recording = True

        logger.debug("Recording started. Waiting for speech...")

        try:
            with sd.InputStream(
                samplerate=sample_rate,
                channels=1,
                dtype="float32",
                blocksize=chunk_samples,
                device=config.INPUT_DEVICE_INDEX,
            ) as stream:
                while recording:
                    chunk, overflowed = stream.read(chunk_samples)
                    audio_chunk = chunk[:, 0]
                    audio_buffer.append(audio_chunk.copy())

                    # Check voice activity using VAD or RMS
                    is_voice = False
                    if self._vad:
                        try:
                            # VAD takes 16-bit PCM integer chunks
                            int16_chunk = (np.clip(audio_chunk, -1.0, 1.0) * 32767).astype(np.int16)
                            vad_score = float(self._vad.predict(int16_chunk))
                            is_voice = vad_score > 0.4
                        except Exception:
                            rms = float(np.sqrt(np.mean(audio_chunk ** 2)))
                            is_voice = rms >= config.SILENCE_THRESHOLD
                    else:
                        rms = float(np.sqrt(np.mean(audio_chunk ** 2)))
                        is_voice = rms >= config.SILENCE_THRESHOLD

                    if is_voice:
                        speech_chunk_count += 1
                        silence_counter = 0
                    else:
                        silence_counter += 1

                    # Trigger streaming partial callback if user provided one
                    if on_partial_audio and speech_chunk_count > 0 and len(audio_buffer) % 15 == 0:
                        try:
                            accumulated = np.concatenate(audio_buffer, axis=0)
                            on_partial_audio(accumulated)
                        except Exception:
                            pass

                    # Stop once minimum speech is followed by silence threshold
                    if speech_chunk_count >= min_speech_chunks and silence_counter >= silence_chunks:
                        recording = False
                        logger.debug(
                            f"End of speech detected ({speech_chunk_count} speech chunks, "
                            f"{silence_counter} silence chunks). Finalizing."
                        )

                    # Initial silence timeout (user didn't say anything)
                    if timeout_chunks and speech_chunk_count < min_speech_chunks and silence_counter >= timeout_chunks:
                        logger.debug("Active timeout reached with no speech.")
                        return np.array([], dtype=np.float32)

                    # Hard cutoff
                    if len(audio_buffer) >= max_duration_chunks:
                        recording = False
                        logger.warning("Max recording duration reached (30s).")

                    # Instant abort on typed HUD command
                    from modules.api_server import hud_server
                    if not hud_server.command_queue.empty():
                        logger.debug("Typed command received via HUD. Aborting mic recording.")
                        return np.array([], dtype=np.float32)

            if not audio_buffer:
                return np.array([], dtype=np.float32)

            audio = np.concatenate(audio_buffer, axis=0).astype(np.float32)
            logger.debug(f"Recorded {len(audio) / sample_rate:.2f}s of audio.")
            return audio

        except Exception as exc:
            logger.error(f"Recording failed: {exc}")
            return np.array([], dtype=np.float32)

    def transcribe(self, audio: np.ndarray) -> str:
        """
        Transcribe audio array to text using faster-whisper.
        """
        if audio.size == 0:
            return ""

        def _run(model):
            segments, _ = model.transcribe(
                audio,
                beam_size=1,
                language="en",
                vad_filter=True,
                vad_parameters={"min_silence_duration_ms": 250},
            )
            return " ".join(seg.text.strip() for seg in segments).strip()

        try:
            return _run(self._model)
        except RuntimeError as exc:
            if "CUDA" in str(exc) or "cublas" in str(exc).lower():
                logger.warning(f"CUDA transcription error: {exc}. Retrying on CPU.")
                cpu_model = WhisperModel(
                    config.WHISPER_MODEL_SIZE,
                    device="cpu",
                    compute_type="int8",
                    cpu_threads=config.WHISPER_THREADS,
                )
                return _run(cpu_model)
            logger.error(f"Transcription error: {exc}", exc_info=True)
            return ""
        except Exception as exc:
            logger.error(f"Transcription failed: {exc}", exc_info=True)
            return ""

    def listen(self, timeout: Optional[float] = None, save_path: Optional[str] = None) -> str:
        """
        Record audio until silence and return transcribed text.
        """
        audio = self.record_until_silence(timeout=timeout)
        if audio.size == 0:
            return ""

        if save_path:
            try:
                import soundfile as sf
                sf.write(save_path, audio, config.SAMPLE_RATE)
            except Exception as e:
                logger.warning(f"Failed to save audio file: {e}")

        return self.transcribe(audio)
