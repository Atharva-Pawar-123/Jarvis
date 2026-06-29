import logging
import threading
import queue
import re
import io
import time
try:
    import sounddevice as sd
except ImportError:
    logging.warning("sounddevice not installed, TTS playback will not work.")
    sd = None

from piper.voice import PiperVoice
import config

class StreamingTextToSpeech:
    """
    Streaming TTS Engine.
    Speaks tokens as soon as a complete sentence is formed by the LLM.
    Zero blocking on the main LLM streaming loop.
    """
    def __init__(self):
        try:
            self.voice = PiperVoice.load(config.PIPER_MODEL_PATH, config.PIPER_CONFIG_PATH)
        except Exception as e:
            logging.error(f"Failed to load Piper TTS model: {e}")
            self.voice = None
            
        self.audio_queue = queue.Queue()
        self.stop_event = threading.Event()
        self.sentence_buffer = ""
        self.is_speaking = False
        
        # Sentence boundaries: . ! ? or ... followed by a space
        self.sentence_pattern = re.compile(r'([.!?]|\.\.\.)\s+')
        
        # Start playback thread
        if sd:
            threading.Thread(target=self._audio_player_loop, daemon=True).start()
        
        logging.info("Streaming TTS engine initialized.")

    def _audio_player_loop(self):
        while True:
            if self.stop_event.is_set():
                while not self.audio_queue.empty():
                    try:
                        self.audio_queue.get_nowait()
                    except queue.Empty:
                        break
                time.sleep(0.1)
                continue

            try:
                # Block until audio is available
                audio_array = self.audio_queue.get(timeout=0.5)
                self.is_speaking = True
                
                if not self.stop_event.is_set():
                    sd.play(audio_array, config.TTS_OUTPUT_RATE)
                    sd.wait() # Block this thread until the sentence finishes
                
                self.is_speaking = False
            except queue.Empty:
                continue
            except Exception as e:
                logging.error(f"Error playing audio chunk: {e}")
                self.is_speaking = False

    def on_token(self, token: str):
        """Called by LLM on every new token."""
        self.sentence_buffer += token
        
        # Check if we hit a sentence boundary
        match = self.sentence_pattern.search(self.sentence_buffer)
        if match:
            split_point = match.end()
            sentence = self.sentence_buffer[:split_point]
            self.sentence_buffer = self.sentence_buffer[split_point:]
            
            cleaned = self.strip_for_voice(sentence)
            if cleaned.strip():
                threading.Thread(target=self._synthesize_and_queue, args=(cleaned,), daemon=True).start()

    def _synthesize_and_queue(self, text: str):
        if not self.voice or self.stop_event.is_set():
            return
            
        try:
            # Piper synthesize returns an iterator of AudioChunk objects
            audio_stream = self.voice.synthesize(text)
            import numpy as np
            
            frames = []
            for chunk in audio_stream:
                if self.stop_event.is_set():
                    return
                # Extract raw 16-bit PCM bytes
                frames.append(chunk.audio_int16_bytes)
                
            if frames and not self.stop_event.is_set():
                raw_bytes = b"".join(frames)
                audio_array = np.frombuffer(raw_bytes, dtype=np.int16)
                self.audio_queue.put(audio_array)
                
        except Exception as e:
            logging.error(f"Piper synthesis error: {e}")

    def speak(self, text: str, blocking: bool = True):
        """Non-streaming use for simple responses."""
        if not self.voice or not sd:
            logging.info(f"[TTS Output]: {text}")
            return
            
        cleaned = self.strip_for_voice(text)
        if not cleaned.strip():
            return
            
        self._synthesize_and_queue(cleaned)
        
        if blocking:
            while not self.audio_queue.empty() or self.is_speaking:
                time.sleep(0.1)

    def stop(self):
        self.stop_event.set()
        if sd:
            sd.stop()
        
        # Clear queue
        while not self.audio_queue.empty():
            try:
                self.audio_queue.get_nowait()
            except queue.Empty:
                break
                
        self.sentence_buffer = ""
        self.is_speaking = False
        # Reset event so it can play again
        self.stop_event.clear()

    def strip_for_voice(self, text: str) -> str:
        """Removes markdown and unpronounceable characters."""
        text = text.replace("e.g.", "for example")
        text = text.replace("i.e.", "that is")
        
        # Remove markdown symbols
        for char in ["**", "*", "#", "`", "_", "~", "|"]:
            text = text.replace(char, "")
            
        # Replace URLs
        text = re.sub(r'https?://[^\s]+', 'the link', text)
        
        return text.strip()

    def flush(self):
        """Synthesize whatever is left in the buffer at the end of generation."""
        if self.sentence_buffer.strip():
            cleaned = self.strip_for_voice(self.sentence_buffer)
            if cleaned.strip():
                self._synthesize_and_queue(cleaned)
            self.sentence_buffer = ""
            
        # Wait for queue to empty so JARVIS finishes speaking before returning control
        while not self.audio_queue.empty() or self.is_speaking:
            time.sleep(0.1)
