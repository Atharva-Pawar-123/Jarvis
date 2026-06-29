"""
JARVIS — Just A Rather Very Intelligent System
===============================================
Local AI assistant with voice, vision, and automation.

Run with:
    cd D:\\JARVIS
    .\\venv\\Scripts\\Activate.ps1
    python main.py

Architecture:
    - Wake word ("Hey JARVIS") → OpenWakeWord (background thread)
    - Speech-to-Text → faster-whisper (CUDA)
    - Intent Classification → Ollama/Mistral (low temperature)
    - LLM Responses → Ollama/Mistral 7B
    - Text-to-Speech → Piper TTS (deep male voice)
    - Vision → Moondream2 (lazy-loaded, screen + webcam)
    - Automation → PyAutoGUI + ctypes + subprocess
    - Email → Gmail SMTP
    - WhatsApp → pywhatkit (WhatsApp Web)
"""

import os
# Force pure-python implementation to bypass Protobuf version mismatch between TF and Gemini
os.environ["PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION"] = "python"
# Force Ollama to use CPU only — prevents CUDA crashes when GPU drivers are missing/broken
os.environ["CUDA_VISIBLE_DEVICES"] = ""
import gc
import logging
import psutil
import re
import signal
import subprocess
import sys
from pynput import keyboard
import threading
import time
import webbrowser
from pathlib import Path

import config
from modules.memory import ConversationMemory
from modules.tts import TextToSpeech
from modules.stt import SpeechToText
from modules.gaming import GamingMonitor
from modules.llm import LLMEngine
from modules.vision import VisionEngine
from modules.email_handler import EmailHandler
from modules.whatsapp_handler import WhatsAppHandler
from modules.automation import AutomationEngine
from modules.intent import IntentClassifier, PROTECTED_INTENTS
from modules.wake_word import WakeWordDetector
from modules.image_gen import ImageGenerationEngine
from modules.web_search import WebSearchEngine
from modules.hud import JarvisHUD
from modules.tray import JarvisTray
from modules.long_term_memory import LongTermMemory
from modules.browser import BrowserController
from modules.news import get_news
from modules.scheduler import ReminderScheduler
from modules.weather import get_weather
from modules.location import get_current_location
from modules.voice_auth import VoiceAuthenticator
from modules.document_reader import DocumentReader
from modules.gallery import ImageGallery
from modules.powershell_handler import PowerShellHandler
from modules.routine_manager import RoutineManager
from modules.iot_handler import IoTHandler
from modules.sentiment import SentimentAnalyzer
from modules.analytics import AnalyticsEngine
from modules.kairos import KairosEngine
from modules.ultraplan import UltraPlanCoordinator
from modules.buddy import BuddyEngine
from modules.search_engine import SearchEngine
from modules.skill_loader import SkillLoader
from modules.mcp.manager import PluginManager
from modules.cost_tracker import CostTracker
from modules.api_server import hud_server as global_hud_server
import datetime


# ---------------------------------------------------------------------------
# Logging security filter
# ---------------------------------------------------------------------------
class SensitiveDataFilter(logging.Filter):
    """
    Redacts sensitive information like API keys and emails from logs.
    """
    def filter(self, record):
        msg = str(record.msg)
        
        # Redact common API key patterns (32-40 hex chars)
        msg = re.sub(r'[a-f0-9]{32,40}', '[REDACTED_API_KEY]', msg, flags=re.IGNORECASE)
        
        # Redact emails
        msg = re.sub(r'[\w\.-]+@[\w\.-]+\.\w+', '[REDACTED_EMAIL]', msg)
        
        # Redact passwords/keys in typical JSON/env formats
        msg = re.sub(r'(password|key|token|secret)["\s:]+[\w\.-]+', r'\1: [REDACTED]', msg, flags=re.IGNORECASE)
        
        record.msg = msg
        return True


# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------
def _setup_logging() -> None:
    """Configure logging to write to LOG_PATH and print to console."""
    log_path = Path(config.LOG_PATH)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    log_format = "[%(asctime)s] [%(levelname)s] %(name)s — %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    logging.basicConfig(
        level=getattr(logging, config.LOG_LEVEL, logging.INFO),
        format=log_format,
        datefmt=date_format,
        handlers=[
            logging.FileHandler(str(log_path), encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )

    # Add sensitivity filter to all handlers
    for handler in logging.root.handlers:
        handler.addFilter(SensitiveDataFilter())


def broadcast_to_hud(data: dict):
    """Safe way to broadcast from synchronous code without loop conflicts."""
    global_hud_server.emit(data)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Startup banner
# ---------------------------------------------------------------------------
BANNER = r"""
   _____   ___  ______      _______ _____ 
  |_   _| / _ \ | ___ \    / /_   _/  ___|
    | |  / /_\ \| |_/ /   / /  | | \ `--. 
    | |  |  _  ||    /   / /   | |  `--. \
   _| |_ | | | || |\ \  / /   _| |_/\__/ /
   \___/ \_| |_/\_| \_|/_/    \___/\____/ 
                                          
             [ ARC REACTOR ACTIVE ]
           SYSTEM VERSION: 2.1.0-STABLE
           ==========================
"""


def main() -> None:
    """
    JARVIS main entry point.

    Initializes all subsystems, starts the wake word listener, and
    runs the main voice command loop until shutdown is requested or
    Ctrl+C is pressed.
    """
    _setup_logging()
    print(BANNER)
    logger.info("JARVIS starting up...")
    
    # --- RESOURCE GUARD: Priority Management ---
    try:
        p = psutil.Process(os.getpid())
        # Set to Normal priority so it has equal footing with other apps
        if sys.platform == 'win32':
            p.nice(psutil.NORMAL_PRIORITY_CLASS)
        else:
            p.nice(0)
        logger.info("Process priority set to NORMAL for responsiveness.")
    except Exception as exc:
        logger.warning(f"Failed to set process priority: {exc}")
    
    # HUD WebSocket Server is now started on-demand via voice command
    logger.info("HUD WebSocket server is in standby.")

    # -----------------------------------------------------------------------
    # Skill loader and MCP Plugins
    # -----------------------------------------------------------------------
    skill_loader = SkillLoader()
    
    mcp_manager = None
    if getattr(config, "MCP_ENABLED", False):
        try:
            print("Starting MCP Ecosystem...")
            mcp_manager = PluginManager()
            mcp_manager.start_all()
        except Exception as exc:
            logger.error(f"Failed to start MCP Manager: {exc}")

    # -----------------------------------------------------------------------
    # Component initialization
    # -----------------------------------------------------------------------
    try:
        hud = JarvisHUD()
    except Exception as exc:
        logger.warning(f"HUD init warning: {exc}")
        hud = None

    if hud:
        hud.set_status("INITIALIZING", "#FF8C00")
        hud.set_jarvis_text("Initializing systems...")

    logger.info("Initializing Search Engine...")
    search_engine = SearchEngine()

    logger.info("Initializing Dynamic Skill Framework...")
    skill_loader = SkillLoader()
    browser_controller = None

    try:
        lt_memory = LongTermMemory()
    except Exception as exc:
        logger.warning(f"Long-term memory init warning: {exc}")
        lt_memory = None

    try:
        # Build the Master System Prompt with dynamic user profile injection
        user_profile = ""
        if lt_memory:
            user_profile = "\nUSER PROFILE:\n" + lt_memory.get_user_profile_summary() + "\n"
        
        # Default to Work mode on startup
        current_mode = "work"
        mode_instruction = "\n" + config.SYSTEM_MODES.get(current_mode, "") + "\n"
        
        enhanced_prompt = config.JARVIS_SYSTEM_PROMPT + user_profile + mode_instruction
        
        if lt_memory:
            context = lt_memory.get_context_string()
            if context:
                enhanced_prompt += f"\nRELEVANT USER FACTS (Internal Use Only):\n{context}\n"
            
        memory = ConversationMemory(
            max_turns=config.MAX_HISTORY_TURNS,
            system_prompt=enhanced_prompt
        )
    except Exception as exc:
        logger.exception("Failed to initialize conversation memory.")
        print(f"[ERROR] Memory initialization failed: {exc}")
        sys.exit(1)

    try:
        tts = TextToSpeech()
    except FileNotFoundError as exc:
        logger.error(str(exc))
        print(f"\n[ERROR] {exc}\n")
        sys.exit(1)
    except Exception as exc:
        logger.exception("Failed to initialize TTS engine.")
        print(f"[ERROR] TTS initialization failed: {exc}")
        sys.exit(1)

    try:
        stt = SpeechToText()
    except Exception as exc:
        logger.exception("Failed to initialize STT engine.")
        tts.speak("I'm having trouble loading my speech recognition engine.")
        print(f"[ERROR] STT initialization failed: {exc}")
        sys.exit(1)

    try:
        llm = LLMEngine()
    except RuntimeError as exc:
        logger.error(str(exc))
        print(f"\n[ERROR] {exc}\n")
        print("Make sure Ollama is running: open a terminal and run 'ollama serve'")
        sys.exit(1)
    except Exception as exc:
        logger.exception("Failed to initialize LLM engine.")
        print(f"[ERROR] LLM initialization failed: {exc}")
        sys.exit(1)

    try:
        vision = VisionEngine()
    except Exception as exc:
        logger.warning(f"Vision engine init warning (non-fatal): {exc}")
        vision = None

    try:
        email_handler = EmailHandler()
    except Exception as exc:
        logger.warning(f"Email handler init warning (non-fatal): {exc}")
        email_handler = EmailHandler.__new__(EmailHandler)
        email_handler._address = ""
        email_handler._password = ""

    try:
        whatsapp_handler = WhatsAppHandler()
    except Exception as exc:
        logger.warning(f"WhatsApp handler init warning (non-fatal): {exc}")
        whatsapp_handler = None

    try:
        automation = AutomationEngine()
    except Exception as exc:
        logger.warning(f"Automation engine init warning (non-fatal): {exc}")
        automation = None

    try:
        image_gen = ImageGenerationEngine()
    except Exception as exc:
        logger.warning(f"Image generation engine init warning: {exc}")
        image_gen = None

    try:
        web_search = WebSearchEngine()
    except Exception as exc:
        logger.warning(f"Web search engine init warning: {exc}")
        web_search = None

    def _shutdown_callback():
        import _thread
        _thread.interrupt_main()

    try:
        # pylint: disable=unused-variable
        tray = JarvisTray(callbacks={
            "toggle_hud": lambda: hud.toggle() if hud else None,
            "shutdown": _shutdown_callback
        })
    except Exception as exc:
        logger.warning(f"Tray init warning: {exc}")
        tray = None  # noqa: F841

    try:
        intent_classifier = IntentClassifier()
    except Exception as exc:
        logger.exception("Failed to initialize intent classifier.")
        print(f"[ERROR] Intent classifier failed: {exc}")
        sys.exit(1)

    try:
        analytics = AnalyticsEngine()
    except Exception as exc:
        logger.warning(f"Analytics engine init warning: {exc}")
        analytics = None

    # Core Extended Components
    try:
        # LongTermMemory was already initialized at line 142
        # We only need to initialize the others
        doc_reader = DocumentReader()
        gallery_viewer = ImageGallery(config.IMAGE_SAVE_DIR)
        authenticator = VoiceAuthenticator()
        # Deferred callback — patched after speak_interruptible is defined below
        _reminder_callback_holder = [tts.speak]
        scheduler = ReminderScheduler(tts_callback=lambda t: _reminder_callback_holder[0](t))

        browser = BrowserController()
        
        # Sprint 6 Components
        powershell = PowerShellHandler(llm_engine=llm)
        routine_manager = RoutineManager()
        iot_handler = IoTHandler()
        sentiment_analyzer = SentimentAnalyzer()

        if hud:
            hud.set_jarvis_text("All systems green. Standing by.")
            hud.set_status("ONLINE", "#00FFFF")
    except Exception as exc:
        logger.warning(f"Extended components init warning: {exc}")
        doc_reader = None
        gallery_viewer = None
        authenticator = None
        scheduler = None
        browser = None
        powershell = None
        routine_manager = None
        iot_handler = None
        sentiment_analyzer = SentimentAnalyzer() # Sentiment is small/safe to try again or fallback to neutral logic

    logger.info("All components initialized successfully.")

    # -----------------------------------------------------------------------
    # Wake word detection — threading event for inter-thread communication
    # -----------------------------------------------------------------------
    listening_event = threading.Event()
    is_muted = False
    manual_mute = False

    def toggle_mute(force_state: bool = None, is_auto: bool = False) -> None:
        nonlocal is_muted, manual_mute
        
        if force_state is not None:
            new_state = force_state
        else:
            new_state = not is_muted
            
        # If the user triggered this manually, track their preference
        if not is_auto:
            manual_mute = new_state
            
        # If auto-unmuting but the user manually muted earlier, don't unmute
        if is_auto and not new_state and manual_mute:
            logger.info("Gaming mode ended, but keeping system MUTED due to prior manual mute.")
            return

        if is_muted != new_state:
            is_muted = new_state
            if is_muted:
                broadcast_to_hud({"state": "MUTED"})
                if not is_auto:
                    speak_interruptible("Muted, sir.")
                else:
                    logger.info("Gaming mode activated. Auto-muting microphone.")
                    # Optional visual-only notification
                    broadcast_to_hud({"type": "alert", "color": "cyan", "message": "GAMING MODE: AUTO-MUTED"})
            else:
                broadcast_to_hud({"state": "LISTENING"})
                if not is_auto:
                    speak_interruptible("Listening again, sir.")
                else:
                    logger.info("Gaming mode deactivated. Microphone restored.")
                    broadcast_to_hud({"type": "alert", "color": "cyan", "message": "GAMING MODE: ENDED"})

    def on_game_state_change(is_gaming: bool):
        toggle_mute(force_state=is_gaming, is_auto=True)

    # Initialize Gaming Monitor
    gaming_monitor = GamingMonitor(callback=on_game_state_change)
    gaming_monitor.start()

    def on_key_press(key):
        if key == keyboard.Key.f4:
            toggle_mute()

    # Start keyboard listener for F4
    kb_listener = keyboard.Listener(on_press=on_key_press)
    kb_listener.daemon = True
    kb_listener.start()

    def on_wake_word_detected() -> None:
        """Callback invoked by the wake word detector on the background thread."""
        if is_muted:
            logger.info("Wake word detected but system is MUTED. Ignoring.")
            return

        logger.info("Wake word event triggered.")
        # Barge-in: immediately kill any ongoing TTS playback
        try:
            tts.stop()
            # Small delay to let audio hardware settle before mic opens
            import time
            time.sleep(0.4)
        except Exception:
            pass
        listening_event.set()

    # -----------------------------------------------------------------------
    # Wake word detector startup
    # -----------------------------------------------------------------------
    try:
        wake_word_detector = WakeWordDetector(callback=on_wake_word_detected)
        wake_word_detector.start()
    except Exception as exc:
        logger.exception("Failed to start wake word detector.")
        print(f"[ERROR] Wake word detector failed: {exc}")
        sys.exit(1)

    # -----------------------------------------------------------------------
    # Graceful shutdown handler (Ctrl+C / SIGINT)
    # -----------------------------------------------------------------------
    def shutdown_handler(sig, frame) -> None:
        """Handle Ctrl+C and SIGINT for graceful shutdown."""
        logger.info("SIGINT received — shutting down gracefully.")
        wake_word_detector.stop()
        print("\nJARVIS offline.")
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown_handler)

    # -----------------------------------------------------------------------
    # -----------------------------------------------------------------------
    # Shared TTS Utility
    # -----------------------------------------------------------------------
    def speak_interruptible(text: str, blocking: bool = True) -> None:
        """
        Speak while allowing wake word barge-in.
        Momentarily resumes the wake word engine during TTS so the user 
        can interrupt JARVIS by saying the wake word.
        Automatically applies emotional inflection based on content.
        """
        # Immediate interruption: stop any ongoing speech before starting new one
        tts.stop()
        
        if hud:
            hud.set_status("SPEAKING", "#4da6ff")
            hud.set_jarvis_text(text)
        
        print(f"JARVIS: {text}")
        
        broadcast_to_hud({
            "state": "SPEAKING",
            "assistant_reply": text
        })
        
        # Determine emotion and get TTS parameters
        emotion = sentiment_analyzer.analyze(text)
        tts_params = sentiment_analyzer.get_tts_params(emotion)
        
        # We no longer pause the wake word detector here.
        # This allows for "Always-Active" barge-in so the user can interrupt JARVIS.
        tts.speak(text, blocking=blocking, temp_length_scale=tts_params.get("length_scale"))

    # -----------------------------------------------------------------------
    # Self-Correction & Context Helpers
    # -----------------------------------------------------------------------
    def handle_self_correction(current_text: str, conversation_memory: ConversationMemory) -> str:
        """
        If user says 'I meant...', 'Actually...', etc., use LLM to fix previous turn.
        """
        lower_text = current_text.lower()
        trigger_words = ["i meant", "actually", "correction", "not that", "i mean"]
        
        if any(word in lower_text for word in trigger_words):
            logger.info("Self-correction detected. Reframing request...")
            # Get last user message
            last_user_msg = ""
            for msg in reversed(conversation_memory._history):
                if msg["role"] == "user":
                    last_user_msg = msg["content"]
                    break
            
            if not last_user_msg:
                return current_text
                
            refine_prompt = f"The user previously said: '{last_user_msg}'. Now they say: '{current_text}'. Combine these into a single corrected intent. Return ONLY the corrected command text."
            corrected = llm.generate([{"role": "user", "content": refine_prompt}])
            logger.info(f"Corrected command: {corrected}")
            return str(corrected).strip()
            
        return current_text

    def get_confirmation(prompt_text: str) -> bool:
        """
        Ask the user for confirmation and return True if they agree.
        """
        speak_interruptible(prompt_text)
        # Briefly wait for response
        response = stt.listen(timeout=5)
        if not response:
            return False
            
        lower_resp = response.lower()
        affirmative = ["yes", "yeah", "do it", "go ahead", "proceed", "yep", "sure", "ok", "okay", "execute", "correct"]
        return any(word in lower_resp for word in affirmative)

    # Patch scheduler to use speak_interruptible now that it's defined
    if scheduler and '_reminder_callback_holder' in dir():
        _reminder_callback_holder[0] = speak_interruptible


    # -----------------------------------------------------------------------
    # System Health Monitor (Background)
    # -----------------------------------------------------------------------
    def health_monitor_loop():
        import psutil
        import time
        last_alert_time = 0
        last_hud_update = 0
        HUD_INTERVAL = 5      # push resource stats to HUD every 5 seconds
        ALERT_INTERVAL = 120  # check for critical alerts every 2 minutes
        ALERT_SPEAK_COOLDOWN = 600  # speak alert at most once per 10 minutes

        # Optionally probe VRAM via pynvml
        _nvml_ok = False
        try:
            import pynvml
            pynvml.nvmlInit()
            _gpu_handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            _nvml_ok = True
        except Exception:
            _gpu_handle = None

        def get_vram_pct():
            if _nvml_ok:
                try:
                    mem = pynvml.nvmlDeviceGetMemoryInfo(_gpu_handle)
                    return round(mem.used / mem.total * 100, 1)
                except Exception:
                    pass
            return None  # unavailable

        while True:
            try:
                now = time.time()

                # --- HUD resource telemetry (lightweight, frequent) ---
                if now - last_hud_update >= HUD_INTERVAL:
                    cpu  = psutil.cpu_percent()          # non-blocking
                    ram  = psutil.virtual_memory().percent
                    vram = get_vram_pct()

                    hud_payload = {
                        "resources": {
                            "cpu":  round(cpu, 1),
                            "ram":  round(ram, 1),
                        },
                        "modules": {
                            "stt": True, "tts": True, "llm": True, "vision": True
                        },
                        "cost": {
                            "usd": CostTracker.get().get_today_cost(),
                            "limit": getattr(config, "DAILY_API_BUDGET_USD", 0.5)
                        }
                    }
                    if vram is not None:
                        hud_payload["resources"]["vram"] = vram

                    broadcast_to_hud(hud_payload)
                    last_hud_update = now

                # --- Critical alert checks (heavier, infrequent) ---
                if now - last_alert_time >= ALERT_INTERVAL:
                    cpu  = psutil.cpu_percent(interval=0.5)  # brief sample
                    ram  = psutil.virtual_memory().percent
                    battery = psutil.sensors_battery()

                    alerts = []
                    if cpu > 98:
                        alerts.append("CPU usage is critically high.")
                    if ram > 98:
                        alerts.append("System memory is almost exhausted.")
                    if battery and battery.percent < 15 and not battery.power_plugged:
                        alerts.append(f"Battery is low at {int(battery.percent)} percent.")

                    if alerts and (now - last_alert_time > ALERT_SPEAK_COOLDOWN):
                        msg = "I have a system health warning. " + " ".join(alerts)
                        logger.warning(f"Health Alert: {msg}")
                        broadcast_to_hud({"state": "ALERT"})
                        speak_interruptible(msg)
                        last_alert_time = now
                    elif alerts:
                        last_alert_time = now  # reset timer without speaking

            except Exception as exc:
                logger.error(f"Health monitor error: {exc}")

            time.sleep(5)  # tight loop sleep; logic above controls actual work intervals

    health_thread = threading.Thread(target=health_monitor_loop, daemon=True)
    health_thread.start()
    logger.info("System health monitor active.")

    # -----------------------------------------------------------------------
    # Memory and Speech Helpers
    # -----------------------------------------------------------------------
    def record_and_speak(user_input: str, assistant_msg: str, intent_name: str = "chat"):
        """Unify memory recording and speech synthesis."""
        # Add to short-term conversation memory
        memory.add_user_message(user_input)
        memory.add_assistant_message(assistant_msg)
        
        # Add to long-term semantic memory (background)
        if lt_memory:
            lt_memory.extract_facts_background(user_input, assistant_msg, llm)
            
        # Speak it
        print(f"JARVIS: {assistant_msg}")
        speak_interruptible(assistant_msg)


    # -----------------------------------------------------------------------
    # Dynamic Greeting Engine
    # -----------------------------------------------------------------------
    def generate_greeting() -> str:
        now = datetime.datetime.now()
        hour = now.hour
        
        if 5 <= hour < 12:
            period = "morning"
        elif 12 <= hour < 18:
            period = "afternoon"
        else:
            period = "evening"
            
        user_name = "sir"
        if lt_memory:
            user_name = lt_memory.get_kv("user_name") or "sir"
            
        greeting = f"Good {period}, {user_name}. JARVIS is online and ready. "
        
        # Proactive: Check for reminders
        if scheduler and scheduler.reminders:
            count = len(scheduler.reminders)
            greeting += f"You have {count} reminder{'s' if count > 1 else ''} on the schedule. "
            
        return greeting

    speak_interruptible(generate_greeting())
    logger.info("JARVIS is live and listening for wake word.")

    # Start KAIROS engine
    kairos = KairosEngine(
        tts_callback=lambda msg: speak_interruptible(msg, blocking=False),
        hud_callback=broadcast_to_hud if config.ENABLE_HUD else None
    )
    kairos.start()
    
    # Initialize ULTRAPLAN Coordinator
    ultraplan = UltraPlanCoordinator(
        llm_engine=llm,
        tts_callback=lambda msg: speak_interruptible(msg, blocking=False),
        hud_callback=broadcast_to_hud if config.ENABLE_HUD else None
    )

    # Initialize BUDDY companion
    buddy = BuddyEngine()
    print("\n--- JARVIS COMPANION (BUDDY) ---")
    print(buddy.get_info())
    print("--------------------------------\n")
    
    # Inject BUDDY into the base system prompt
    current_prompt = memory.system_prompt
    memory.update_system_prompt(current_prompt + buddy.get_system_prompt_addition())

    # -----------------------------------------------------------------------
    # Main event loop
    # -----------------------------------------------------------------------
    while True:
        try:
            # --- Check HUD typed command queue (non-blocking) ---
            try:
                hud_cmd = global_hud_server.command_queue.get_nowait()
                if hud_cmd == "__TOGGLE_MUTE__":
                    toggle_mute()
                elif hud_cmd:
                    # Treat it as a spoken command bypassing STT entirely
                    logger.info(f"HUD typed command received: {hud_cmd!r}")
                    broadcast_to_hud({"type": "transcription", "text": hud_cmd})
                    listening_event.set()   # trigger normal intent processing
                    # Store the typed command so the listen block can pick it up
                    # We use a thread-safe flag to pass the text to stt.listen bypass
                    _queued_hud_text = hud_cmd
            except Exception:
                _queued_hud_text = None

            # Wait for wake word with a short timeout so Ctrl+C still works
            triggered = listening_event.wait(timeout=0.1)

            if not triggered:
                continue

            # Immediate interruption: Stop JARVIS from speaking if user says wake word
            tts.stop()
            
            listening_event.clear()

            # Self-healing: Ensure critical modules are alive
            if intent_classifier is None:
                try:
                    logger.info("Self-healing: Re-initializing intent classifier...")
                    intent_classifier = IntentClassifier()
                except Exception:
                    pass

            # We no longer pause the wake word detector here.
            # This enables continuous "barge-in" support.

            try:
                # If a typed command arrived from the HUD, skip the mic prompt
                if _queued_hud_text:
                    _text_for_turn = _queued_hud_text
                    _queued_hud_text = None
                else:
                    speak_interruptible("Yes?")
                    _text_for_turn = None

                # --- CONTINUOUS ACTIVE LOOP ---
                while True:
                    # Clear any lingering interrupt flags before opening mic
                    listening_event.clear()

                    if hud:
                        hud.set_status("LISTENING", "#00FFFF")

                    broadcast_to_hud({"state": "LISTENING"})

                    if _text_for_turn:
                        # Use pre-queued text, bypass microphone
                        user_text = _text_for_turn
                        _text_for_turn = None
                    else:
                        user_text = stt.listen(timeout=config.ACTIVE_TIMEOUT_SECONDS)

                    # Start timing the command for analytics
                    command_start_time = time.time()

                    if not user_text:
                        # Timeout reached
                        logger.info("Active timeout reached. Going to sleep.")
                        speak_interruptible("Listening suspended. Going to sleep.")
                        listening_event.clear() # clear any barge-in flags that got trapped
                        break

                    if len(user_text.strip()) < 2:
                        # Ignore tiny glitches, but keep actively listening
                        continue

                    # Filter out redundant wake word if it was captured in the stream
                    wake_pat = re.compile(rf"^{config.WAKE_WORD_MODEL}\b", re.IGNORECASE)
                    user_text = wake_pat.sub("", user_text.strip()).strip()
                    
                    if not user_text:
                        # If user ONLY said the wake word, just prompt for more
                        speak_interruptible("Yes, sir? I'm listening.")
                        continue

                    # Phase 2: Handle Self-Correction
                    user_text = handle_self_correction(user_text, memory)

                    logger.info(f"User said: {user_text}")
                    print(f"\nYou: {user_text}")
                    
                    if hud:
                        hud.set_user_text(user_text)
                        hud.set_status("THINKING", "#FFFF00")
                    
                    broadcast_to_hud({
                        "state": "THINKING",
                        "last_command": user_text
                    })

                    # Classify intent with conversation context
                    try:
                        # Build recent context string (last 3 messages) to resolve pronouns/context
                        recent_history = memory.get_messages()[-3:]
                        ctx_lines = [f"{m['role']}: {m['content']}" for m in recent_history if m['role'] != 'system']
                        intent_context = "\n".join(ctx_lines)
                        
                        result = intent_classifier.classify(user_text, context=intent_context)
                        intent = result.get("intent", "chat")
                        entities = result.get("entities", {})
                        logger.info(f"Intent: {intent} | Entities: {entities}")
                    except Exception as exc:
                        logger.error(f"Intent classification error: {exc}", exc_info=True)
                        intent = "chat"
                        entities = {}
                    
                    broadcast_to_hud({
                        "intent": intent,
                        "confidence": 95 # Mock for now
                    })

                    # --- CORE STABILITY MONITOR ---
                    if (llm and llm.is_degraded) or (intent_classifier and intent_classifier.is_degraded):
                        broadcast_to_hud({
                            "type": "alert",
                            "message": "CORE DEGRADED: LOCAL BACKUP ACTIVE",
                            "color": "red"
                        })
                        # Reset flags for next turn
                        if llm: llm.is_degraded = False
                        if intent_classifier: intent_classifier.is_degraded = False

                    # ------------------------------------------------------------------
                    # Module Safety Checks
                    # ------------------------------------------------------------------
                    missing_module = False
                    if intent in ["take_screenshot", "volume_up", "volume_down", "mute", "copy_clipboard", "paste_clipboard", "clear_clipboard", "create_file", "create_folder", "move_file", "rename_file", "delete_item", "list_folder", "get_system_status"] and automation is None:
                        speak_interruptible("Automation engine is offline.")
                        missing_module = True
                    elif intent == "execute_powershell" and powershell is None:
                        speak_interruptible("PowerShell module is offline.")
                        missing_module = True
                    elif intent == "start_routine" and routine_manager is None:
                        speak_interruptible("Routine manager is offline.")
                        missing_module = True
                    elif intent == "control_iot" and iot_handler is None:
                        speak_interruptible("IoT handler is offline.")
                        missing_module = True
                        
                    if missing_module:
                        continue
                        
                    # ------------------------------------------------------------------
                    # Intent dispatch
                    # ------------------------------------------------------------------
                    try:
                        # Security check for sensitive commands
                        if intent in PROTECTED_INTENTS and authenticator:
                            logger.info(f"Protected intent '{intent}' triggered. Requesting authorization...")
                            
                            if not authenticator.is_enrolled():
                                speak_interruptible("This is a protected command. However, your voice is not yet enrolled. Please say 'enroll my voice' to begin.")
                                continue

                            speak_interruptible("Identity verification required. Please speak for confirmation.")
                            test_path = "logs/auth_attempt.wav"
                            # We record and save the audio for speaker verification
                            stt.listen(timeout=5, save_path=test_path)
                            
                            if authenticator.verify(test_path):
                                logger.info("Voice authorization granted.")
                            else:
                                speak_interruptible("Voice identity could not be verified. Access denied.")
                                continue

                        match intent:
                            case "enroll_voice":
                                if authenticator is None:
                                    speak_interruptible("Voice authentication module is offline.")
                                else:
                                    speak_interruptible("Beginning enrollment. Please speak clearly for five seconds starting now, sir.")
                                    enroll_path = "data/enrollment/user_gold.wav"
                                    # Ensure the enrollment directory exists
                                    import pathlib
                                    pathlib.Path("data/enrollment").mkdir(parents=True, exist_ok=True)
                                    stt.listen(timeout=7, save_path=enroll_path)
                                    if authenticator.enroll(enroll_path):
                                        speak_interruptible("Voice enrollment complete. Your identity is now secured, sir.")
                                    else:
                                        speak_interruptible("I'm sorry. Enrollment failed. Please try again.")

                            case "switch_mode":
                                new_mode = entities.get("mode", "").lower().replace("mode", "").strip()
                                if new_mode in config.SYSTEM_MODES:
                                    current_mode = new_mode
                                    mode_instruction = "\n" + config.SYSTEM_MODES[new_mode] + "\n"
                                    user_profile = ""
                                    if lt_memory:
                                        user_profile = "\nUSER PROFILE:\n" + lt_memory.get_user_profile_summary() + "\n"
                                    
                                    # Rebuild the system prompt
                                    new_full_prompt = config.JARVIS_SYSTEM_PROMPT + user_profile + mode_instruction
                                    if lt_memory:
                                        context = lt_memory.get_context_string()
                                        if context:
                                            new_full_prompt += f"\nRELEVANT USER FACTS (Internal Use Only):\n{context}\n"
                                    
                                    memory.update_system_prompt(new_full_prompt)
                                    # Broadcast mode change to HUD
                                    broadcast_to_hud({
                                        "type": "mode_change",
                                        "mode": new_mode
                                    })
                                    response = f"Switching to {new_mode} mode, sir. How can I assist you in this configuration?"
                                    speak_interruptible(response)
                                else:
                                    response = f"I'm sorry, sir. I don't have a configuration for {new_mode} mode."
                                    speak_interruptible(response)

                            case "shutdown":
                                speak_interruptible("Shutting down. Goodbye.")
                                logger.info("Shutdown command received.")
                                wake_word_detector.stop()
                                break
                            
                            case "extract_text":
                                if vision is None:
                                    speak_interruptible("Vision engine is offline.")
                                else:
                                    speak_interruptible("Scanning the screen for text.", blocking=False)
                                    text = vision.extract_text()
                                    print(f"JARVIS: {text}")
                                    speak_interruptible(f"I found the following text: {text}")

                            case "read_document":
                                if doc_reader is None:
                                    speak_interruptible("Document reader is offline.")
                                else:
                                    path = entities.get("file_path") or entities.get("source_path") or ""
                                    if not path:
                                        speak_interruptible("Which document should I read?")
                                    else:
                                        speak_interruptible("Reading and indexing the document.", blocking=False)
                                        content = doc_reader.read(path)
                                        
                                        # Index in semantic memory for later Q&A
                                        if lt_memory:
                                            chunks = doc_reader.chunk_text(content)
                                            for chunk in chunks:
                                                lt_memory.store_semantic(chunk, metadata={"source": path})
                                        
                                        # Provide an immediate summary
                                        summary_req = f"Summarize this document content: {content[:2000]}"
                                        memory.add_user_message(summary_req)
                                        response = llm.generate(memory.get_messages())
                                        memory.add_assistant_message(response)
                                        print(f"JARVIS: {response}")
                                        speak_interruptible(response)

                            case "show_gallery":
                                if gallery_viewer is None:
                                    speak_interruptible("Gallery viewer is offline.")
                                else:
                                    msg = gallery_viewer.open()
                                    speak_interruptible(msg)

                            case "clear_memory":
                                memory.clear()
                                speak_interruptible("Conversation memory cleared.")

                            case "tell_time":
                                now = datetime.datetime.now()
                                response = f"The time is {now.strftime('%I:%M %p')}."
                                print(f"JARVIS: {response}")
                                speak_interruptible(response)
                                
                            case "ultraplan":
                                speak_interruptible("Activating ULTRAPLAN Coordinator, sir. Please stand by while I consult the swarm.", blocking=False)
                                task_query = entities.get("query") or user_text
                                ultraplan.execute_plan_async(task_query)


                            case "tell_date":
                                now = datetime.datetime.now()
                                response = f"Today is {now.strftime('%A, %B %d, %Y')}."
                                print(f"JARVIS: {response}")
                                speak_interruptible(response)

                            case "get_weather":
                                loc = entities.get("location", "").strip()
                                speak_interruptible(f"Checking the weather for {loc if loc else 'your area'}.", blocking=False)
                                response = get_weather(loc)
                                print(f"JARVIS: {response}")
                                speak_interruptible(response)

                            case "set_reminder":
                                if scheduler is None:
                                    speak_interruptible("Reminder service is offline.")
                                else:
                                    time_str = entities.get("time", "").strip()
                                    task = entities.get("text", "").strip() or user_text
                                    if not time_str:
                                        speak_interruptible("When should I remind you?")
                                    else:
                                        response = scheduler.add_reminder(time_str, task)
                                        print(f"JARVIS: {response}")
                                        speak_interruptible(response)

                            case "get_news":
                                speak_interruptible("Fetching today's top stories.", blocking=False)
                                report = get_news()
                                print(f"JARVIS: {report}")
                                speak_interruptible(report)

                            case "open_website":
                                if browser is None:
                                    speak_interruptible("Browser automation is offline.")
                                else:
                                    url = entities.get("url", "").strip()
                                    if not url:
                                        speak_interruptible("Which website should I open?")
                                    else:
                                        msg = browser.open_url(url)
                                        speak_interruptible(msg)

                            case "open_dashboard":
                                url = "http://127.0.0.1:8080"
                                
                                # Step 1: Start the server if it isn't running
                                if not global_hud_server.is_running():
                                    speak_interruptible("Spinning up the dashboard server.", blocking=False)
                                    global_hud_server.start(host="127.0.0.1", port=8080)
                                    logger.info("HUD server started on-demand.")
                                    
                                    # Wait for uvicorn to actually bind to the port
                                    import urllib.request
                                    server_ready = False
                                    for attempt in range(10):
                                        time.sleep(0.5)
                                        try:
                                            urllib.request.urlopen(f"{url}/api/health", timeout=1)
                                            server_ready = True
                                            break
                                        except Exception:
                                            pass
                                    
                                    if not server_ready:
                                        logger.error("HUD server failed to become ready after 5 seconds.")
                                        speak_interruptible("The dashboard server failed to start, sir. Please check the logs.")
                                        continue
                                
                                # Step 2: Force-open a NEW browser window (not a background tab)
                                try:
                                    if sys.platform == "win32":
                                        # On Windows, use os.startfile or subprocess to guarantee
                                        # a visible window — webbrowser.open() often fires into
                                        # a hidden/minimized existing instance
                                        subprocess.Popen(
                                            ["cmd", "/c", "start", "", url],
                                            shell=False,
                                            creationflags=subprocess.CREATE_NO_WINDOW
                                        )
                                    else:
                                        webbrowser.open_new(url)
                                    speak_interruptible("Dashboard activated, sir.")
                                except Exception as wb_exc:
                                    logger.error(f"Failed to open browser: {wb_exc}")
                                    speak_interruptible(f"The dashboard is running at {url}, sir, but I couldn't launch your browser.")

                            case "close_dashboard":
                                if global_hud_server.is_running():
                                    global_hud_server.stop()
                                    logger.info("HUD server stopped.")
                                
                                if browser:
                                    browser.close()
                                    speak_interruptible("Dashboard terminated, sir.")
                                else:
                                    speak_interruptible("I've stopped the dashboard server, sir. Please close the browser tab manually.")

                            case "search_browser":
                                if browser is None:
                                    speak_interruptible("Browser automation is offline.")
                                else:
                                    query = entities.get("query", "").strip() or user_text
                                    msg = browser.search(query)
                                    speak_interruptible(msg)

                            case "take_screenshot":
                                path = automation.take_screenshot()
                                response = "Screenshot saved."
                                print(f"JARVIS: {response} ({path})")
                                speak_interruptible(response)

                            case "describe_screen":
                                if vision is None:
                                    speak_interruptible("Vision engine is not available.")
                                else:
                                    # Vision task proceed
                                    
                                    speak_interruptible("Analyzing the screen.", blocking=False)
                                    description = vision.describe_screen()
                                    memory.add_user_message(user_text)
                                    memory.add_assistant_message(description)
                                    print(f"JARVIS: {description}")
                                    speak_interruptible(description)

                                    if lt_memory:
                                        lt_memory.extract_facts_background(user_text, description, llm)

                            case "answer_screen":
                                if vision is None:
                                    speak_interruptible("Vision engine is not available.")
                                else:
                                    question = entities.get("question", "") or user_text
                                    speak_interruptible("Looking at the screen.", blocking=False)
                                    answer = vision.answer_about_screen(question)
                                    record_and_speak(user_text, answer, intent)

                            case "describe_webcam":
                                if vision is None:
                                    speak_interruptible("Vision engine is not available.")
                                else:
                                    speak_interruptible("Activating camera.", blocking=False)
                                    answer = vision.answer_about_webcam(user_text)
                                    record_and_speak(user_text, answer, intent)

                            case "send_email":
                                if not email_handler.is_configured():
                                    response = (
                                        "Email is not configured. "
                                        "Please add your Gmail credentials to the .env file."
                                    )
                                    print(f"JARVIS: {response}")
                                    speak_interruptible(response)
                                else:
                                    confirmation = email_handler.compose_and_send(entities)
                                    record_and_speak(user_text, confirmation, intent)

                            case "read_emails":
                                if not email_handler.is_configured():
                                    speak_interruptible("I cannot read your emails. Please configure your Gmail in the environment file.")
                                else:
                                    speak_interruptible("Checking your inbox now.", blocking=False)
                                    report = email_handler.read_emails()
                                    record_and_speak(user_text, report, intent)

                            case "send_whatsapp":
                                if whatsapp_handler is None:
                                    speak_interruptible("WhatsApp integration is offline, sir.")
                                else:
                                    confirmation = whatsapp_handler.compose_and_send(entities)
                                    record_and_speak(user_text, confirmation, intent)

                            case "type_text":
                                if automation is None:
                                    speak_interruptible("Automation is offline, sir.")
                                else:
                                    text_to_type = entities.get("text", "").strip()
                                    if text_to_type:
                                        result_msg = automation.type_text(text_to_type)
                                        print(f"JARVIS: {result_msg}")
                                        speak_interruptible(result_msg)
                                    else:
                                        response = "What would you like me to type, sir?"
                                        print(f"JARVIS: {response}")
                                        speak_interruptible(response)

                            case "open_app":
                                if automation is None:
                                    speak_interruptible("Automation is offline, sir.")
                                else:
                                    app_entities = entities.get("app_name", "").strip()
                                    if not app_entities:
                                        speak_interruptible("Which application should I open, sir?")
                                    else:
                                        # Support multiple apps: "Open Chrome and Notepad"
                                        apps = [a.strip() for a in re.split(r',|and|&', app_entities) if a.strip()]
                                        for app in apps:
                                            result_msg = automation.open_app(app)
                                            print(f"JARVIS: {result_msg}")
                                            speak_interruptible(result_msg, blocking=False)

                            case "volume_up":
                                result_msg = automation.volume_up()
                                record_and_speak(user_text, result_msg, intent)

                            case "volume_down":
                                result_msg = automation.volume_down()
                                record_and_speak(user_text, result_msg, intent)

                            case "mute":
                                result_msg = automation.mute_toggle()
                                record_and_speak(user_text, result_msg, intent)

                            case "generate_image":
                                if image_gen is None:
                                    speak_interruptible("My image generation engine is offline.")
                                else:
                                    prompt_text = entities.get("prompt_text", "").strip() or user_text
                                    try:
                                        count = int(entities.get("count", 1))
                                    except (ValueError, TypeError):
                                        count = 1
                                    
                                    if count > 1:
                                        speak_interruptible(f"Generating {count} images for you in the background, sir. I will notify you when the full set is ready.")
                                    else:
                                        speak_interruptible("Drawing that for you, sir.", blocking=False)
                                    
                                    def bg_generate_batch(p, c):
                                        success_count = 0
                                        for i in range(c):
                                            # For batch, only open the first one automatically, or none
                                            res = image_gen.generate_image(p, llm=llm, auto_open=(c == 1))
                                            if "finished" in res:
                                                success_count += 1
                                        
                                        if c > 1:
                                            if success_count > 0:
                                                msg = f"Sir, I have finished generating your batch of {success_count} images. They are ready for your review in the designated folder."
                                                # Open the folder for convenience
                                                try:
                                                    os.startfile(config.IMAGE_SAVE_DIR)
                                                except:
                                                    pass
                                            else:
                                                msg = "Sir, I'm afraid I encountered an error while generating the image batch."
                                            
                                            speak_interruptible(msg)

                                    # Start background thread
                                    threading.Thread(target=bg_generate_batch, args=(prompt_text, count), daemon=True).start()

                            case "speak_faster":
                                msg = tts.increase_speed()
                                record_and_speak(user_text, msg, intent)

                            case "speak_slower":
                                msg = tts.decrease_speed()
                                record_and_speak(user_text, msg, intent)

                            case "copy_clipboard":
                                # Copy the last JARVIS response to clipboard if available
                                last_response = ""
                                for msg in reversed(memory._history):
                                    if msg["role"] == "assistant":
                                        last_response = msg["content"]
                                        break
                                msg = automation.copy_clipboard(last_response)
                                record_and_speak(user_text, msg, intent)

                            case "paste_clipboard":
                                msg = automation.paste_clipboard()
                                record_and_speak(user_text, f"The clipboard contains: {msg}", intent)

                            case "read_clipboard":
                                msg = automation.paste_clipboard()
                                record_and_speak(user_text, f"The clipboard says: {msg}", intent)

                            case "clear_clipboard":
                                msg = automation.clear_clipboard()
                                record_and_speak(user_text, msg, intent)

                            case "create_file":
                                path = entities.get("destination_path") or entities.get("file_name") or "new_file.txt"
                                msg = automation.create_file(path)
                                record_and_speak(user_text, msg, intent)

                            case "create_folder":
                                path = entities.get("destination_path") or entities.get("folder_name") or "new_folder"
                                msg = automation.create_folder(path)
                                record_and_speak(user_text, msg, intent)

                            case "move_file":
                                source = entities.get("source_path") or entities.get("file_name") or ""
                                dest = entities.get("destination_path") or entities.get("folder_name") or ""
                                msg = automation.move_file(source, dest)
                                record_and_speak(user_text, msg, intent)

                            case "rename_file":
                                source = entities.get("source_path") or ""
                                new_name = entities.get("file_name") or entities.get("destination_path") or ""
                                msg = automation.rename_file(source, new_name)
                                record_and_speak(user_text, msg, intent)

                            case "delete_file" | "delete_folder":
                                path = entities.get("source_path") or entities.get("file_name") or entities.get("folder_name") or ""
                                msg = automation.delete_item(path)
                                record_and_speak(user_text, msg, intent)

                            case "list_folder":
                                path = entities.get("source_path") or entities.get("folder_name") or "."
                                msg = automation.list_folder(path)
                                record_and_speak(user_text, msg, intent)

                            case "web_search":
                                query = entities.get("query") or user_text
                                msg = web_search.quick_search(query) if web_search else "Web search is offline."
                                record_and_speak(user_text, msg, intent)

                            case "open_search":
                                query = entities.get("query") or user_text
                                msg = web_search.open_search(query) if web_search else "Web search is offline."
                                record_and_speak(user_text, msg, intent)

                            case "system_status":
                                msg = automation.get_system_status()
                                print(f"JARVIS: {msg}")
                                speak_interruptible(msg)

                            case "execute_powershell":
                                cmd = entities.get("command") or user_text
                                
                                # YOLO Classifier check
                                speak_interruptible("Running YOLO security analysis on the command...", blocking=False)
                                risk_assessment = powershell.classify_risk(cmd)
                                
                                if risk_assessment["risk"] == "LOW":
                                    speak_interruptible("Command classified as low risk. Auto-approving execution.", blocking=False)
                                    msg = powershell.execute(cmd)
                                    print(f"JARVIS: {msg}")
                                    speak_interruptible(msg)
                                else:
                                    # Medium or High risk requires voice confirmation
                                    speak_interruptible(f"Sir, this command is classified as {risk_assessment['risk']} risk. {risk_assessment['explanation']} Do I have your permission to execute it?")
                                    
                                    # Block and listen for user response
                                    auth_response = stt.listen(timeout=10)
                                    if not auth_response:
                                        speak_interruptible("I did not receive a response, sir. Cancelling execution.")
                                        continue
                                        
                                    resp_lower = auth_response.lower()
                                    affirmative_words = ["yes", "yeah", "do it", "go ahead", "proceed", "yep", "sure", "ok", "okay", "execute"]
                                    
                                    if any(word in resp_lower for word in affirmative_words):
                                        speak_interruptible("Executing now, sir.", blocking=False)
                                        msg = powershell.execute(cmd)
                                        print(f"JARVIS: {msg}")
                                        speak_interruptible(msg)
                                    else:
                                        speak_interruptible("Execution cancelled, sir.")

                            case "start_routine":
                                r_name = entities.get("routine_name") or ""
                                r_intents = routine_manager.get_routine(r_name)
                                if not r_intents:
                                    msg = f"I couldn't find a routine named {r_name}."
                                    speak_interruptible(msg)
                                else:
                                    speak_interruptible(f"Starting your {r_name}.")
                                    # For simplicity, we just trigger the main dispatcher recursively or loop here
                                    # Since this is a simple POC, we'll just log and speak
                                    for r_step in r_intents:
                                        logger.info(f"Routine step: {r_step['intent']}")
                                        # Note: A real implementation would recursively call the dispatcher
                                    speak_interruptible(f"The {r_name} is complete.")

                            case "control_iot":
                                dev = entities.get("iot_device") or ""
                                act = entities.get("iot_action") or ""
                                msg = iot_handler.control_device(dev, act)
                                print(f"JARVIS: {msg}")
                                speak_interruptible(msg)

                            case "get_mood":
                                msg = vision.detect_mood() if vision else "Vision is offline."
                                print(f"JARVIS: {msg}")
                                speak_interruptible(f"you appear to be feeling {msg}.")

                            case "system_report":
                                if analytics:
                                    msg = analytics.get_summary()
                                    print(f"JARVIS: {msg}")
                                    speak_interruptible(msg)
                                else:
                                    speak_interruptible("Analytics system is offline, sir.")

                            case "get_location":
                                speak_interruptible("Locating your current position, sir.", blocking=False)
                                loc_data = get_current_location()
                                if loc_data["status"] == "success":
                                    msg = f"You are currently in {loc_data['city']}, {loc_data['country']}, sir. Coordinates are {loc_data['lat']} latitude and {loc_data['lon']} longitude."
                                    print(f"JARVIS: {msg}")
                                    speak_interruptible(msg)
                                    
                                    # Broadcast to HUD to center map
                                    broadcast_to_hud({
                                        "type": "location",
                                        "data": {
                                            "lat": loc_data["lat"],
                                            "lon": loc_data["lon"],
                                            "city": loc_data["city"]
                                        }
                                    })
                                else:
                                    speak_interruptible("I'm sorry, sir. I'm unable to determine your precise location at the moment.")

                            case "search_codebase":
                                query = entities.get("query") or entities.get("object") or user_text.replace("search for", "").replace("search", "").strip()
                                if not query:
                                    speak_interruptible("What would you like me to search for, sir?")
                                else:
                                    speak_interruptible(f"Searching the codebase for {query}...", blocking=False)
                                    results = search_engine.search_codebase(query)
                                    
                                    # Output to terminal
                                    print(f"JARVIS: Search Results:\n{results}")
                                    
                                    # Tell the user we found something
                                    if "No matches" in results:
                                        speak_interruptible(f"I found no matches for '{query}', sir.")
                                    else:
                                        # Count lines of results roughly
                                        count = len([line for line in results.splitlines() if line and not line.startswith("...")])
                                        speak_interruptible(f"I found {count} matches for '{query}'. I have displayed them in the terminal.")

                            case "api_cost":
                                # Report Gemini API token usage and estimated spend
                                from modules.cost_tracker import CostTracker as _CT
                                _tracker = _CT.get()
                                msg = _tracker.format_voice_summary()
                                verbose_log = _tracker.format_summary(verbose=True)
                                logger.info(f"[CostTracker] {verbose_log}")
                                print(f"JARVIS: {msg}")
                                print(verbose_log)
                                speak_interruptible(msg)

                            case "open_incognito":
                                url = entities.get("url", "")
                                if not browser_controller:
                                    from modules.browser import BrowserController
                                    browser_controller = BrowserController()
                                msg = browser_controller.open_incognito(url=url)
                                print(f"JARVIS: {msg}")
                                speak_interruptible(msg)

                            case "mute_toggle":
                                toggle_mute()

                            case _ if intent in skill_loader.get_dynamic_intents():
                                # Delegate to dynamic skill plugin
                                msg = skill_loader.handle_intent(intent, entities, user_text)
                                print(f"JARVIS: {msg}")
                                speak_interruptible(msg)


                            case _:
                                # Default: general conversation or autonomous tool calling via LLM
                                memory.add_user_message(user_text)
                                
                                # Phase 2: Enhanced RAG (Retrieval Augmented Generation)
                                # Inject semantic long-term memory context if available
                                if lt_memory:
                                    # We now query context for EVERY turn to ensure JARVIS 'remembers'
                                    context = lt_memory.get_context_string(query=user_text)
                                    if context:
                                        # Rebuild dynamic prompt with profile + mode + retrieved context
                                        user_profile = lt_memory.get_user_profile_summary()
                                        mode_instruction = config.SYSTEM_MODES.get(current_mode, "")
                                        
                                        full_prompt = config.JARVIS_SYSTEM_PROMPT + \
                                                      f"\nUSER PROFILE (Internal Use Only - Do Not Repeat):\n{user_profile}\n" + \
                                                      f"\nCURRENT MODE: {current_mode}\n" + \
                                                      f"\nRELEVANT USER FACTS (Internal Reference - Do Not List):\n{context}\n" + \
                                                      "\nIMPORTANT: Do not mention the context or user profile headers in your response. Use the information to be more helpful and personal."
                                        
                                        memory.update_system_prompt(full_prompt)
                                
                                messages = memory.get_messages()
                                
                                # -----------------------------------------------------------
                                # Phase 4: MCP Autonomous Tool Calling Loop
                                # -----------------------------------------------------------
                                max_tool_iterations = 5
                                current_iter = 0
                                
                                while current_iter < max_tool_iterations:
                                    current_iter += 1
                                    
                                    # Get active tools from the MCP ecosystem
                                    tools_schema = mcp_manager.get_all_tools_schema() if mcp_manager else []
                                    
                                    if tools_schema:
                                        logger.info(f"Invoking LLM with {len(tools_schema)} tools...")
                                        try:
                                            result = llm.generate_with_tools(messages, tools=tools_schema)
                                        except Exception as exc:
                                            logger.error(f"Tool generation failed: {exc}")
                                            speak_interruptible("My reasoning engine encountered an error while processing tools.")
                                            break
                                            
                                        text_resp = result.get("content", "")
                                        tool_calls = result.get("tool_calls", [])
                                        
                                        if text_resp and not tool_calls:
                                            # This is the FINAL answer — speak it
                                            logger.info(f"LLM Final Response: {text_resp[:150]}")
                                            memory.add_assistant_message(text_resp)
                                            print(f"JARVIS: {text_resp}")
                                            speak_interruptible(text_resp)
                                        elif text_resp:
                                            # Intermediate thought during tool loop — log only, don't speak
                                            logger.info(f"LLM Tool-Phase Thought (suppressed): {text_resp[:150]}")
                                            memory.add_assistant_message(text_resp)
                                            
                                        if not tool_calls:
                                            # LLM is done calling tools. We have our final answer.
                                            break
                                            
                                        for tc in tool_calls:
                                            tc_name = tc.get("name", "")
                                            tc_args = tc.get("arguments", {})
                                            
                                            logger.info(f"LLM requested tool: {tc_name} with args: {tc_args}")
                                            speak_interruptible(f"Invoking system tool: {tc_name.replace('mcp__', '').replace('__', ' ')}", blocking=False)
                                            
                                            # Execute tool
                                            if tc_name.startswith("mcp__"):
                                                parts = tc_name.split("__", 2)
                                                if len(parts) == 3:
                                                    srv_name, real_tool = parts[1], parts[2]
                                                    import json
                                                    tool_result = mcp_manager.call_tool(srv_name, real_tool, tc_args)
                                                    memory.add_message("tool", json.dumps(tool_result), name=tc_name)
                                                else:
                                                    memory.add_message("tool", '{"error": "Invalid tool name format"}', name=tc_name)
                                            else:
                                                memory.add_message("tool", '{"error": "Unknown tool"}', name=tc_name)
                                                
                                        # Update messages for next iteration
                                        messages = memory.get_messages()
                                    else:
                                        # -----------------------------------------------------------
                                        # Classic Streaming Mode (if no MCP tools loaded)
                                        # -----------------------------------------------------------
                                        try:
                                            # Safe typing handler for generator vs str
                                            response_raw = llm.generate(messages, stream=True)
                                            response_gen = response_raw if hasattr(response_raw, "__iter__") and not isinstance(response_raw, str) else [str(response_raw)]
                                            
                                            print("JARVIS: ", end="", flush=True)
                                            
                                            if hud:
                                                hud.set_status("SPEAKING", "#4da6ff")
                                                
                                            broadcast_to_hud({
                                                "state": "SPEAKING",
                                                "assistant_reply": ""
                                            })
                                            
                                            full_response = []
                                            tts.start_stream()
                                            
                                            for chunk in response_gen:
                                                print(chunk, end="", flush=True)
                                                full_response.append(chunk)
                                                tts.feed_audio(chunk)
                                                
                                            print()
                                            
                                            tts.finish_stream()
                                            final_text = "".join(full_response).strip()
                                            memory.add_assistant_message(final_text)
                                            
                                            broadcast_to_hud({
                                                "state": "IDLE",
                                                "assistant_reply": final_text
                                            })
                                            
                                            # Save to semantic memory
                                            if lt_memory:
                                                lt_memory.extract_facts_background(user_text, final_text, llm)
                                                
                                        except Exception as exc:
                                            logger.error(f"Text generation error: {exc}", exc_info=True)
                                            msg = "I'm sorry, I encountered an error connecting to my core processor."
                                            speak_interruptible(msg)
                                            print(f"JARVIS: {msg}")
                                            
                                        break  # End while loop if we did classic streaming
                        # End timing and log analytics
                        if analytics:
                            latency = time.time() - command_start_time
                            analytics.log_command(intent, latency)
                            
                            # Broadcast stats to HUD
                            stats = analytics.get_stats_for_hud()
                            broadcast_to_hud({"type": "stats", "data": stats})

                        # Manual memory cleanup after every intent execution
                        gc.collect()

                    except FileNotFoundError as exc:
                        error_msg = f"Sir, I couldn't find the required file. {exc}"
                        logger.error(f"FileNotFoundError in intent '{intent if 'intent' in dir() else 'unknown'}': {exc}")
                        broadcast_to_hud({"type": "alert", "color": "red", "message": f"FILE NOT FOUND: {exc}"})
                        speak_interruptible(error_msg)

                    except PermissionError as exc:
                        error_msg = f"Sir, I don't have permission to do that. You may need to run JARVIS as administrator. {exc}"
                        logger.error(f"PermissionError in intent '{intent if 'intent' in dir() else 'unknown'}': {exc}")
                        broadcast_to_hud({"type": "alert", "color": "red", "message": "PERMISSION DENIED"})
                        speak_interruptible(error_msg)

                    except (ConnectionError, TimeoutError) as exc:
                        error_msg = f"Sir, a network connection failed. Please check your internet connection. {exc}"
                        logger.error(f"NetworkError in intent '{intent if 'intent' in dir() else 'unknown'}': {exc}")
                        broadcast_to_hud({"type": "alert", "color": "red", "message": "NETWORK ERROR"})
                        speak_interruptible(error_msg)

                    except Exception as exc:
                        _intent_for_log = intent if 'intent' in dir() else 'unknown'
                        error_type = type(exc).__name__
                        error_msg = f"Sir, I encountered a {error_type} error while handling that request. {str(exc)[:80]}"
                        logger.error(
                            f"Error handling intent '{_intent_for_log}': {exc}", exc_info=True
                        )
                        print(f"[ERROR] {exc}")
                        broadcast_to_hud({"type": "alert", "color": "red", "message": f"{error_type.upper()}: {str(exc)[:40]}"})
                        speak_interruptible(error_msg)

            except Exception as exc:
                # Catch-all for the outer listen/classify block — never crash the loop
                logger.error(f"Unexpected error in main loop: {exc}", exc_info=True)
                try:
                    speak_interruptible("I encountered an unexpected error. I'm attempting to recover.")
                except Exception:
                    pass

            finally:
                # Wake word detector is now always active, but we reset its state
                # after a turn to ensure fresh detection.
                wake_word_detector.resume()

        except Exception as exc:
            logger.error(f"Critical error in main loop turn: {exc}", exc_info=True)
            # Short sleep to prevent infinite rapid-fire loops
            time.sleep(1)
            continue

    # -----------------------------------------------------------------------
    # Clean exit
    # -----------------------------------------------------------------------
    logger.info("JARVIS shutting down.")
    print("JARVIS offline.")

    # Save token cost data before exit
    try:
        from modules.cost_tracker import CostTracker as _CT
        _tracker = _CT.get()
        logger.info(_tracker.format_summary(verbose=True))
        _tracker.save()
    except Exception as _e:
        logger.warning(f"Failed to save cost tracker: {_e}")

    if lt_memory:
        try:
            print("Initiating autoDream memory consolidation...")
            speak_interruptible("Consolidating memories before sleep.", blocking=False)
            lt_memory.auto_dream(llm)
        except Exception as e:
            logger.error(f"Failed to dream: {e}")

    sys.exit(0)

if __name__ == "__main__":
    main()
