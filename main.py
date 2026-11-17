import os
import sys
import time
import logging
import threading
import asyncio
from datetime import datetime
from pathlib import Path

# Local module imports
JARVIS_ROOT = Path(__file__).parent
sys.path.insert(0, str(JARVIS_ROOT))

import config
from server.runtime import JarvisRuntime
from modules.scheduler import ReminderScheduler
from modules.wake_word import WakeWordDetector
from modules.hud import JarvisHUD
from modules.memory import ConversationMemory
from modules.api_server import hud_server

logger = logging.getLogger(__name__)

def main():
    # 1. Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[logging.FileHandler(config.LOG_PATH), logging.StreamHandler(sys.stdout)]
    )
    
    print("=====================================================")
    print("  J.A.R.V.I.S — LOCAL AI SYSTEM ONLINE (V2.1)")
    print("=====================================================")
    
    # 2. Boot Unified JARVIS Runtime
    runtime = JarvisRuntime()
    asyncio.run(runtime.boot())

    dashboard = JarvisHUD()

    def update_hud_state(state: str):
        try:
            dashboard.set_status(state.upper())
        except Exception:
            pass
        
    def update_hud_transcript(sender: str, text: str):
        try:
            if sender == "user":
                dashboard.set_user_text(text)
            else:
                dashboard.set_jarvis_text(text)
        except Exception:
            pass

    scheduler = ReminderScheduler(runtime.tts.speak)
    conversation_memory = ConversationMemory(max_turns=config.MAX_HISTORY_TURNS, system_prompt=config.JARVIS_SYSTEM_PROMPT)

    # Event flag for wake word
    wake_event = threading.Event()
    
    def on_wake_word_detected():
        wake_event.set()

    def on_speech_interrupted():
        logging.info("Voice interruption triggered: Stopping TTS.")
        runtime.tts.stop()
        wake_event.set()
        
    wake_detector = WakeWordDetector(
        callback=on_wake_word_detected,
        on_interrupt=on_speech_interrupted,
        tts_engine=runtime.tts
    )
    
    wake_detector.start()
    hud_server.start()

    # Escape key listener to stop speech
    def _keyboard_interrupt_listener():
        try:
            import msvcrt
            while True:
                if msvcrt.kbhit():
                    key = msvcrt.getch()
                    if key == b'\x1b' and runtime.tts.is_speaking:
                        logging.info("Escape pressed — interrupting JARVIS speech.")
                        runtime.tts.stop()
                time.sleep(0.05)
        except Exception as e:
            logging.warning(f"Keyboard listener failed: {e}")

    threading.Thread(target=_keyboard_interrupt_listener, daemon=True, name="KBD-Interrupt").start()

    runtime.tts.speak("JARVIS unified reasoning core online and ready, sir.")

    # Main Voice Loop
    try:
        while True:
            if not hud_server.command_queue.empty():
                raw_text = hud_server.command_queue.get()
                if raw_text == "__TOGGLE_MUTE__":
                    runtime.automation.mute_toggle()
                    continue
                if raw_text == "__STOP_SPEECH__":
                    runtime.tts.stop()
                    continue
            else:
                wake_event.wait(timeout=0.1)
                if not wake_event.is_set():
                    continue
                
                wake_event.clear()
                update_hud_state("listening")
                
                raw_text = runtime.stt.listen()
                update_hud_state("idle")
                
                if not raw_text or len(raw_text.strip()) < 2:
                    runtime.tts.speak("I didn't catch that, sir.")
                    continue

            print(f"\nYou: {raw_text}")
            update_hud_transcript("user", raw_text)

            # Intent classification check for shutdown
            classified = runtime.intent.classify(raw_text)
            intent_name = classified.get("intent", "chat")

            if intent_name == "shutdown":
                runtime.tts.speak("Shutting down all systems. Goodbye, sir.")
                break

            update_hud_state("thinking")

            # Route through Unified Agent Orchestrator
            history = conversation_memory.get_messages()
            response = asyncio.run(runtime.orchestrator.execute_task(
                query=raw_text,
                conversation_history=history
            ))

            update_hud_state("speaking")
            runtime.tts.speak(response)
            update_hud_state("idle")

            # Keep conversation memory and transcript updated
            conversation_memory.add_user_message(raw_text)
            conversation_memory.add_assistant_message(response)
            update_hud_transcript("jarvis", response)

            # Extract facts in background thread
            threading.Thread(
                target=runtime.memory.extract_and_store_facts,
                args=(raw_text, response),
                daemon=True
            ).start()

    except KeyboardInterrupt:
        print("\nShutting down by user interrupt...")
    finally:
        wake_detector.stop()
        runtime.tts.stop()
        hud_server.stop()

if __name__ == "__main__":
    main()
