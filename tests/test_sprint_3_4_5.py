import sys
import os
from pathlib import Path

# Add project root to path
sys.path.append(str(Path("D:/JARVIS")))

import config
from modules.vision import VisionEngine
from modules.email_handler import EmailHandler
from modules.whatsapp_handler import WhatsAppHandler
from modules.image_gen import ImageGenerationEngine
from modules.long_term_memory import LongTermMemory
from modules.browser import BrowserController
from modules.web_search import WebSearchEngine

def test_sprint_3():
    print("\n=== SPRINT 3: ADVANCED VISION & COMMS ===")
    try:
        print("[1/3] Testing Vision Engine structure...")
        vis = VisionEngine()
        assert hasattr(vis, "capture_screen")
        print("Vision Engine ready.")
        
        print("[2/3] Testing Email Handler...")
        email = EmailHandler()
        print("Email Handler initialized.")
        
        print("[3/3] Testing WhatsApp Handler...")
        wa = WhatsAppHandler()
        print("WhatsApp Handler initialized.")
        
        print("Sprint 3: PASS (Structural)")
    except Exception as e:
        print(f"Sprint 3: FAIL - {e}")

def test_sprint_4():
    print("\n=== SPRINT 4: UI & PERSONALITY ===")
    try:
        print("[1/2] Testing Image Generation integration...")
        igen = ImageGenerationEngine()
        print("Image Gen Engine ready.")
        
        # HUD and Tray are GUI based, we just check imports
        from modules.hud import JarvisHUD
        from modules.tray import JarvisTray
        print("[2/2] UI Modules imported successfully.")
        
        print("Sprint 4: PASS")
    except Exception as e:
        print(f"Sprint 4: FAIL - {e}")

def test_sprint_5():
    print("\n=== SPRINT 5: MEMORY & WEB ===")
    try:
        print("[1/4] Testing Long-Term Memory (RAG)...")
        ltm = LongTermMemory()
        ltm.update_kv("test_key", "test_val")
        assert ltm.get_kv("test_key") == "test_val"
        print("LTM KV Store working.")
        
        print("[2/4] Testing Browser Controller...")
        browser = BrowserController()
        print("Browser Controller initialized.")
        
        print("[3/4] Testing Web Search Engine...")
        ws = WebSearchEngine()
        print("Web Search Engine ready.")
        
        print("[4/4] Testing Document Reader...")
        from modules.document_reader import DocumentReader
        dr = DocumentReader()
        print("Document Reader initialized.")
        
        print("Sprint 5: PASS")
    except Exception as e:
        print(f"Sprint 5: FAIL - {e}")

if __name__ == "__main__":
    test_sprint_3()
    test_sprint_4()
    test_sprint_5()
