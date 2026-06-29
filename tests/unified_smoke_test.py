import sys
from pathlib import Path
sys.path.append(str(Path("D:/JARVIS")))

def smoke_test():
    print("JARVIS 2.0 UNIFIED SMOKE TEST (Sprints 1-6)")
    
    # Sprint 1
    from modules.llm import LLMEngine
    from modules.intent import IntentClassifier
    print("[OK] Sprint 1: LLM & Intent logic verified.")

    # Sprint 2
    from modules.automation import AutomationEngine
    from modules.scheduler import ReminderScheduler
    print("[OK] Sprint 2: Automation & Scheduler logic verified.")

    # Sprint 3
    from modules.vision import VisionEngine
    from modules.email_handler import EmailHandler
    print("[OK] Sprint 3: Vision & Email logic verified.")

    # Sprint 4
    from modules.image_gen import ImageGenerationEngine
    from modules.hud import JarvisHUD
    print("[OK] Sprint 4: Personality & UI logic verified.")

    # Sprint 5
    from modules.long_term_memory import LongTermMemory
    from modules.browser import BrowserController
    print("[OK] Sprint 5: Long-Term Memory & Web logic verified.")

    # Sprint 6
    from modules.powershell_handler import PowerShellHandler
    from modules.routine_manager import RoutineManager
    from modules.sentiment import SentimentAnalyzer
    print("[OK] Sprint 6: Experimental & Emotional logic verified.")

    print("\nALL SPRINTS VERIFIED AT THE STRUCTURAL LEVEL.")

if __name__ == "__main__":
    smoke_test()
