"""
modules/stt.py — JARVIS Speech-to-Text (faster-whisper)
========================================================
Records audio from the default microphone using sounddevice and
transcribes it using faster-whisper running on CUDA (falls back to
CPU on GPU OOM). Uses RMS-based silence detection to automatically
stop recording when the user stops speaking.
"""

import logging
from typing import Optional

import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel

import config

logger = logging.getLogger(__name__)


class SpeechToText:
    """
    Speech recognition engine using faster-whisper.

    Records audio from the microphone, detects end-of-speech via
    silence detection, and returns transcribed text.
    """

    def __init__(self) -> None:
        """
        Load the Whisper model on initialization.

        Uses CUDA by default (WHISPER_DEVICE). Falls back to CPU if CUDA
        is not available. Logs when the model is ready.
        """
        logger.info(
            f"Loading Whisper model '{config.WHISPER_MODEL_SIZE}' "
            f"on {config.WHISPER_DEVICE} ({config.WHISPER_COMPUTE_TYPE})..."
        )
        try:
            self._model = WhisperModel(
                config.WHISPER_MODEL_SIZE,
                device=config.WHISPER_DEVICE,
                compute_type=config.WHISPER_COMPUTE_TYPE,
                cpu_threads=config.WHISPER_THREADS,
                num_workers=1,
            )
            self._device = config.WHISPER_DEVICE
            logger.info("Whisper model loaded and ready.")
        except Exception as exc:
            logger.warning(
                f"Failed to load Whisper on {config.WHISPER_DEVICE}: {exc}. "
                "Falling back to CPU."
            )
            self._model = WhisperModel(
                config.WHISPER_MODEL_SIZE,
                device="cpu",
                compute_type="float32",
                cpu_threads=config.WHISPER_THREADS,
                num_workers=1,
            )
            self._device = "cpu"
            logger.info("Whisper model loaded on CPU (fallback).")

    def record_until_silence(self, timeout: Optional[float] = None) -> np.ndarray:
        """
        Record audio from the default microphone until silence is detected.

        Accumulates audio chunks at SAMPLE_RATE. Recording stops when
        SILENCE_DURATION seconds of continuous silence (RMS below
        SILENCE_THRESHOLD) is detected, but only after at least 0.5
        seconds of speech has been captured. If `timeout` is provided,
        and no speech is detected at all within `timeout` seconds, the
        recording aborts and returns an empty array.

        Args:
            timeout (float, optional): Max seconds to wait for speech to start.

        Returns:
            numpy.ndarray: Recorded audio as a float32 array at SAMPLE_RATE.
        """
        sample_rate = config.SAMPLE_RATE
        chunk_samples = int(sample_rate * config.CHUNK_DURATION_MS / 1000)
        silence_chunks = int(config.SILENCE_DURATION * 1000 / config.CHUNK_DURATION_MS)
        min_speech_chunks = int(0.5 * 1000 / config.CHUNK_DURATION_MS)
        
        timeout_chunks = None
        if timeout:
            timeout_chunks = int(timeout * 1000 / config.CHUNK_DURATION_MS)
            
        max_duration_chunks = int(30.0 * 1000 / config.CHUNK_DURATION_MS) # 30s absolute max

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
                device=config.INPUT_DEVICE_INDEX
            ) as stream:
                while recording:
                    chunk, overflowed = stream.read(chunk_samples)
                    if overflowed:
                        logger.warning("Audio buffer overflowed — some samples may be lost.")

                    audio_chunk = chunk[:, 0]  # mono
                    audio_buffer.append(audio_chunk.copy())

                    rms = float(np.sqrt(np.mean(audio_chunk ** 2)))

                    if rms < config.SILENCE_THRESHOLD:
                        silence_counter += 1
                    else:
                        speech_chunk_count += 1
                        silence_counter = 0

                    # Stop only after capturing some speech followed by silence
                    if (
                        speech_chunk_count >= min_speech_chunks
                        and silence_counter >= silence_chunks
                    ):
                        recording = False
                        logger.debug(
                            f"Silence detected after {speech_chunk_count} speech chunks. "
                            "Stopping recording."
                        )
                    
                    # Check for absolute timeout before any speech has started
                    if timeout_chunks and speech_chunk_count < min_speech_chunks and silence_counter >= timeout_chunks:
                        recording = False
                        logger.debug(f"Reached active timeout ({timeout}s) with no speech. Sleeping.")
                        return np.array([], dtype=np.float32)
                        
                    # Absolute safety cutoff to prevent infinite hang in noisy rooms
                    if len(audio_buffer) >= max_duration_chunks:
                        recording = False
                        logger.warning("Max recording duration reached (30s). Cutting off to prevent hang.")
                        
                    # Instantly abort recording if a typed command is received
                    from modules.api_server import hud_server
                    if not hud_server.command_queue.empty():
                        logger.debug("Typed command received via HUD. Aborting microphone recording.")
                        return np.array([], dtype=np.float32)

            if not audio_buffer:
                return np.array([], dtype=np.float32)
                
            audio = np.concatenate(audio_buffer, axis=0).astype(np.float32)
            logger.debug(f"Recorded {len(audio) / sample_rate:.1f}s of audio.")
            return audio
        except Exception as exc:
            logger.error(f"Recording failed (check mic index {config.INPUT_DEVICE_INDEX}): {exc}")
            return np.array([], dtype=np.float32)

    def transcribe(self, audio: np.ndarray) -> str:
        """
        Transcribe a numpy audio array to text using faster-whisper.

        Attempts transcription on the configured device. If a CUDA
        out-of-memory error occurs, falls back to CPU for this call.

        Args:
            audio (numpy.ndarray): Float32 audio array at SAMPLE_RATE.

        Returns:
            str: Transcribed text, or empty string if nothing was detected.
        """
        def _run_transcription(model: WhisperModel) -> str:
            # Greedy decoding (beam_size=1) is significantly faster and uses less RAM
            beam = 1 # Hardware optimized for 6GB VRAM
            segments, info = model.transcribe(
                audio,
                beam_size=beam,
                language="en",
                vad_filter=True,
                vad_parameters={"min_silence_duration_ms": 300},
            )
            text = " ".join(seg.text.strip() for seg in segments).strip()
            return text

        try:
            text = _run_transcription(self._model)
            logger.debug(f"Transcription: '{text}'")
            return text
        except RuntimeError as exc:
            if "CUDA out of memory" in str(exc):
                logger.warning("CUDA OOM during transcription — falling back to CPU.")
                cpu_model = WhisperModel(
                    config.WHISPER_MODEL_SIZE,
                    device="cpu",
                    compute_type="float32",
                )
                text = _run_transcription(cpu_model)
                logger.debug(f"CPU fallback transcription: '{text}'")
                return text
            else:
                logger.error(f"Transcription runtime error: {exc}", exc_info=True)
                return ""
        except Exception as exc:
            logger.error(f"Transcription failed: {exc}", exc_info=True)
            return ""

    def listen(self, timeout: Optional[float] = None, save_path: Optional[str] = None) -> str:
        """
        Convenience method: record audio until silence, then transcribe.

        Args:
            timeout (float, optional): Auto-sleep timeout if no speech is heard.
            save_path (str, optional): Path to save the recorded wav file.

        Returns:
            str: The transcribed text from the user's speech, or empty string
                 if nothing intelligible was captured or timeout was reached.
        """
        audio = self.record_until_silence(timeout=timeout)
        if audio.size == 0:
            return ""
        
        if save_path:
            import soundfile as sf
            sf.write(save_path, audio, config.SAMPLE_RATE)
            logger.debug(f"Audio saved to {save_path}")

        return self.transcribe(audio)
