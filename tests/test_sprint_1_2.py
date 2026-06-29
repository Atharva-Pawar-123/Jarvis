import sys
import os
import time
from pathlib import Path

# Add project root to path
sys.path.append(str(Path("D:/JARVIS")))

import config
from modules.stt import SpeechToText
from modules.tts import TextToSpeech
from modules.llm import LLMEngine
from modules.intent import IntentClassifier
from modules.automation import AutomationEngine
from modules.scheduler import ReminderScheduler

def test_sprint_1():
    print("\n=== SPRINT 1: THE FOUNDATION ===")
    try:
        print("[1/4] Initializing TTS...")
        tts = TextToSpeech()
        print("TTS Loaded.")
        
        print("[2/4] Initializing STT...")
        stt = SpeechToText()
        print("STT Loaded.")
        
        print("[3/4] Testing LLM...")
        llm = LLMEngine()
        resp = llm.generate([{"role": "user", "content": "Say 'Sprint 1 OK'"}])
        print(f"LLM Response: {resp}")
        
        print("[4/4] Testing Intent Classifier...")
        ic = IntentClassifier()
        res = ic.classify("Hello JARVIS")
        print(f"Intent Result: {res['intent']}")
        
        print("Sprint 1: PASS")
    except Exception as e:
        print(f"Sprint 1: FAIL - {e}")

def test_sprint_2():
    print("\n=== SPRINT 2: PROACTIVE SYSTEM ===")
    try:
        print("[1/3] Testing Automation Stats...")
        auto = AutomationEngine()
        status = auto.get_system_status()
        print(f"Status: {status}")
        
        print("[2/3] Testing Scheduler...")
        def dummy_speak(text): print(f"REMINDER TRIGGERED: {text}")
        sched = ReminderScheduler(tts_callback=dummy_speak)
        msg = sched.add_reminder("in 1 second", "Test Sprint 2")
        print(msg)
        time.sleep(2) # Wait for trigger
        
        print("[3/3] Testing News/Weather (Integration)...")
        from modules.news import get_news
        from modules.weather import get_weather
        news = get_news()
        print(f"News Sample: {news[:100]}...")
        # Weather might fail without key, but we check if it handles it
        weather = get_weather("London")
        print(f"Weather: {weather}")
        
        print("Sprint 2: PASS")
    except Exception as e:
        print(f"Sprint 2: FAIL - {e}")

if __name__ == "__main__":
    test_sprint_1()
    test_sprint_2()
