"""
modules/tts.py — JARVIS Streaming Text-to-Speech (Piper + sounddevice)
======================================================================
Interruptible TTS engine.  Speaks tokens as complete sentences stream in
from the LLM.  Audio is played in small chunks (~50 ms) through a
sounddevice OutputStream so that a stop() call silences JARVIS within
one chunk boundary (~50 ms latency).

Key design:
  • _audio_player_loop pulls synthesised numpy arrays from self.audio_queue.
  • Each array is sliced into CHUNK_FRAMES-sized pieces and fed to the
    OutputStream callback.  Between every chunk, the stop_event is checked.
  • stop() sets stop_event → callback writes silence → sd.stop() is called
    → queue is drained → buffer is cleared → ready for the next utterance.
"""

import logging
import threading
import queue
import re
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

import numpy as np

try:
    import sounddevice as sd
except ImportError:
    logging.warning("sounddevice not installed, TTS playback will not work.")
    sd = None

from piper.voice import PiperVoice
import config

logger = logging.getLogger(__name__)

# ── Playback chunk size (≈50 ms at 22050 Hz) ─────────────────────────
CHUNK_FRAMES = int(config.TTS_OUTPUT_RATE * 0.05)   # 1102 frames


class StreamingTextToSpeech:
    """
    Streaming, interruptible TTS engine.

    Speaks tokens as soon as a complete sentence is formed by the LLM.
    Zero blocking on the main LLM streaming loop.  Any call to stop()
    silences output within ~50 ms and clears all pending sentences.
    """

    def __init__(self) -> None:
        # ── Piper voice ──────────────────────────────────────────────
        try:
            self.voice = PiperVoice.load(
                config.PIPER_MODEL_PATH, config.PIPER_CONFIG_PATH
            )
        except Exception as e:
            logger.error(f"Failed to load Piper TTS model: {e}")
            self.voice = None

        # ── Queues & state ───────────────────────────────────────────
        self.audio_queue: queue.Queue[np.ndarray] = queue.Queue()
        self.stop_event = threading.Event()
        self.sentence_buffer: str = ""
        self.is_speaking: bool = False
        self._is_first_token: bool = True

        # Serialize PiperVoice.synthesize calls (not thread-safe)
        self._synth_lock = threading.Lock()

        # Bounded thread pool for synthesis (max 2 concurrent)
        self._synth_pool = ThreadPoolExecutor(
            max_workers=2, thread_name_prefix="tts-synth"
        )

        # Sentence boundaries: . ! ? or … followed by whitespace
        self.sentence_pattern = re.compile(r'([.!?]|\.\.\.)\s+')

        # ── Start playback thread ────────────────────────────────────
        if sd:
            threading.Thread(
                target=self._audio_player_loop,
                daemon=True,
                name="TTS-Player",
            ).start()

        logger.info("Streaming TTS engine initialized (interruptible).")

    # ─────────────────────────────────────────────────────────────────
    #  Playback — chunked, interruptible
    # ─────────────────────────────────────────────────────────────────
    def _audio_player_loop(self) -> None:
        """Pull full-sentence audio arrays from the queue and play them
        in small ~50 ms chunks so stop() takes effect almost instantly."""
        while True:
            # If stopped, drain the queue and idle
            if self.stop_event.is_set():
                self._drain_queue()
                time.sleep(0.05)
                continue

            try:
                audio_array = self.audio_queue.get(timeout=0.25)
            except queue.Empty:
                continue

            # Got audio — play it chunk by chunk
            self.is_speaking = True
            try:
                self._play_chunked(audio_array)
            except Exception as e:
                logger.error(f"Error during chunked playback: {e}")
            finally:
                self.is_speaking = False

    def _play_chunked(self, audio: np.ndarray) -> None:
        """Play *audio* in CHUNK_FRAMES-sized slices, checking
        stop_event between every slice."""
        total = len(audio)
        offset = 0

        while offset < total:
            if self.stop_event.is_set():
                if sd:
                    try:
                        sd.stop()
                    except Exception:
                        pass
                return   # bail immediately

            end = min(offset + CHUNK_FRAMES, total)
            chunk = audio[offset:end]
            offset = end

            try:
                sd.play(chunk, config.TTS_OUTPUT_RATE)
                # Wait only for this tiny chunk (~50 ms) instead of
                # blocking for the whole sentence.
                sd.wait()
            except Exception as e:
                logger.error(f"sounddevice play error: {e}")
                return

    def _drain_queue(self) -> None:
        """Remove all pending audio from the queue."""
        while True:
            try:
                self.audio_queue.get_nowait()
            except queue.Empty:
                break

    # ─────────────────────────────────────────────────────────────────
    #  Synthesis
    # ─────────────────────────────────────────────────────────────────
    def _synthesize_and_queue(self, text: str) -> None:
        """Synthesize *text* with Piper and push the result to the
        audio queue.  Runs in a thread pool."""
        if not self.voice or self.stop_event.is_set():
            return

        try:
            with self._synth_lock:
                audio_stream = self.voice.synthesize(text)

            frames = []
            for chunk in audio_stream:
                if self.stop_event.is_set():
                    return
                frames.append(chunk.audio_int16_bytes)

            if frames and not self.stop_event.is_set():
                raw = b"".join(frames)
                audio_array = np.frombuffer(raw, dtype=np.int16)
                self.audio_queue.put(audio_array)
        except Exception as e:
            logger.error(f"Piper synthesis error: {e}")

    # ─────────────────────────────────────────────────────────────────
    #  Public API
    # ─────────────────────────────────────────────────────────────────
    def on_token(self, token: str) -> None:
        """Called by the LLM on every new streamed token."""
        if self._is_first_token:
            print("\nJARVIS: ", end="", flush=True)
            self._is_first_token = False
        print(token, end="", flush=True)
        self.sentence_buffer += token

        match = self.sentence_pattern.search(self.sentence_buffer)
        if match:
            split_point = match.end()
            sentence = self.sentence_buffer[:split_point]
            self.sentence_buffer = self.sentence_buffer[split_point:]

            cleaned = self.strip_for_voice(sentence)
            if cleaned.strip():
                self._synth_pool.submit(self._synthesize_and_queue, cleaned)

    def speak(self, text: str, blocking: bool = True) -> None:
        """Non-streaming use for simple / direct responses."""
        print(f"\nJARVIS: {text}")
        if not self.voice or not sd:
            logger.info(f"[TTS Output]: {text}")
            return

        cleaned = self.strip_for_voice(text)
        if not cleaned.strip():
            return

        self._synthesize_and_queue(cleaned)

        if blocking:
            # Wait for playback, but bail immediately on stop()
            while (not self.audio_queue.empty() or self.is_speaking):
                if self.stop_event.is_set():
                    break
                time.sleep(0.05)

    def stop(self) -> None:
        """Immediately silence JARVIS and discard pending speech.

        Safe to call from any thread at any time.  Playback resumes
        normally the next time audio is queued.
        """
        self.stop_event.set()

        # Halt whatever sounddevice is playing right now
        if sd:
            try:
                sd.stop()
            except Exception:
                pass

        # Drain queued sentences
        self._drain_queue()

        # Reset state
        self.sentence_buffer = ""
        self.is_speaking = False

        logger.info("TTS stopped — speech interrupted.")

        # Give player loop thread a moment to see stop_event if it's currently inside play
        time.sleep(0.06)
        self.stop_event.clear()

    def flush(self) -> None:
        """Synthesize whatever is left in the buffer at end-of-generation."""
        if not self._is_first_token:
            print()  # newline after streamed output
            self._is_first_token = True

        if self.sentence_buffer.strip():
            cleaned = self.strip_for_voice(self.sentence_buffer)
            if cleaned.strip():
                self._synthesize_and_queue(cleaned)
            self.sentence_buffer = ""

        # Wait for queue to empty, but respect stop()
        while not self.audio_queue.empty() or self.is_speaking:
            if self.stop_event.is_set():
                break
            time.sleep(0.05)

    def strip_for_voice(self, text: str) -> str:
        """Remove markdown and unpronounceable characters."""
        text = text.replace("e.g.", "for example")
        text = text.replace("i.e.", "that is")

        for char in ["**", "*", "#", "`", "_", "~", "|"]:
            text = text.replace(char, "")

        text = re.sub(r'https?://[^\s]+', 'the link', text)
        return text.strip()
