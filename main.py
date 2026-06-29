import os
import sys
import time
import logging
import threading
import signal
from datetime import datetime

# Local module imports
import config
from modules.llm import IntelligentLLMEngine
from modules.tts import StreamingTextToSpeech
from modules.long_term_memory import HybridRAGMemory
from modules.stt import SpeechToText
from modules.intent import DualModelIntentClassifier
from modules.react_agent import ReActAgent
from modules.ultraplan import UltraPlanCoordinator

# Tool Modules
from modules.vision import VisionEngine
from modules.email_handler import EmailHandler
from modules.whatsapp_handler import WhatsAppHandler
from modules.automation import AutomationEngine
from modules.code_engine import CodeEngine
from modules.scheduler import ReminderScheduler
from modules.wake_word import WakeWordDetector
from modules.web_search import WebSearchEngine
from modules.browser import BrowserController
from modules.image_gen import ImageGenerationEngine
from modules.gaming import GamingMonitor
from modules.iot_handler import IoTHandler
from modules.weather import get_weather
from modules.news import get_news
from modules.hud import JarvisHUD
from modules.memory import ConversationMemory
from modules.api_server import hud_server

def build_tool_registry(automation, email_handler, whatsapp_handler, web_search, browser, vision, memory, scheduler, image_gen, game_manager, iot_handler, dashboard, weather, news, code_engine):
    """Builds a dictionary of tools to pass to the ReAct agent."""
    return {
        "tell_time": {"func": lambda: f"The time is {datetime.now().strftime('%I:%M %p')}, sir.", "desc": "Get current time"},
        "tell_date": {"func": lambda: f"Today is {datetime.now().strftime('%A, %B %d, %Y')}, sir.", "desc": "Get current date"},
        "open_app": {"func": lambda app_name: automation.open_app(app_name), "desc": "Open an application"},
        "close_app": {"func": lambda app_name: automation.close_app(app_name), "desc": "Close an application"},
        "volume_up": {"func": lambda: automation.volume_up(), "desc": "Increase system volume"},
        "volume_down": {"func": lambda: automation.volume_down(), "desc": "Decrease system volume"},
        "mute": {"func": lambda: automation.mute_toggle(), "desc": "Mute or unmute volume"},
        "take_screenshot": {"func": lambda: automation.take_screenshot(), "desc": "Take a screenshot"},
        "type_text": {"func": lambda text: automation.type_text(text), "desc": "Type text into active window"},
        "system_status": {"func": lambda: automation.system_status(), "desc": "Check CPU, RAM, Disk"},
        "create_file": {"func": lambda file_path, text: automation.create_file(file_path, text), "desc": "Create a file with text"},
        "read_file": {"func": lambda file_path: automation.read_file(file_path), "desc": "Read text from a file"},
        "delete_file": {"func": lambda file_path: hitl_gate("delete_file", automation.delete_file, file_path), "desc": "Delete a file"},
        "send_email": {"func": lambda to, subject, text: email_handler.compose_and_send({"to": to, "subject": subject, "text": text}), "desc": "Send an email"},
        "web_search": {"func": lambda query: web_search.search_and_answer(query), "desc": "Search the web"},
        "open_url": {"func": lambda url: browser.open_url(url), "desc": "Open a URL in browser"},
        "describe_screen": {"func": lambda: vision.describe_screen(), "desc": "Analyze what is on the screen"},
        "read_screen_text": {"func": lambda: vision.ocr_screen(), "desc": "OCR text from screen"},
        "search_memory": {"func": lambda query: memory.search(query), "desc": "Search past conversation memory"},
        "ingest_document": {"func": lambda file_path: memory.ingest_document(file_path), "desc": "Read a PDF, DOCX, or TXT into memory"},
        "set_reminder": {"func": lambda time, reminder_msg: scheduler.add_reminder(time, reminder_msg), "desc": "Set a reminder"},
        "generate_image": {"func": lambda text: image_gen.generate_image(text), "desc": "Generate an image"},
        "control_iot": {"func": lambda iot_device, iot_action: iot_handler.control(iot_device, iot_action), "desc": "Control smart home devices"},
        "weather": {"func": lambda city: get_weather(city), "desc": "Get current weather for a city"},
        "get_news": {"func": lambda: get_news(), "desc": "Get top news headlines"},
    }

def main():
    # 1. Setup logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s',
                        handlers=[logging.FileHandler(config.LOG_PATH), logging.StreamHandler(sys.stdout)])
    
    # 2. Load .env is handled in config
    # 3. Print JARVIS boot banner
    print("=====================================================")
    print("  J.A.R.V.I.S — LOCAL AI SYSTEM ONLINE")
    print("=====================================================")
    
    # Define HUD update closures
    def update_hud_state(state: str):
        try:
            dashboard.set_status(state.upper())
        except Exception: pass
        
    def update_hud_transcript(sender: str, text: str):
        try:
            if sender == "user":
                dashboard.set_user_text(text)
            else:
                dashboard.set_jarvis_text(text)
        except Exception: pass
    
    # 4. Initialize Core Components
    tts = StreamingTextToSpeech()
    memory = HybridRAGMemory(None) # we set LLM later to avoid circular dependency initially, but wait, HybridRAG needs LLM to embed.
    
    llm = IntelligentLLMEngine(
        system_prompt=config.JARVIS_SYSTEM_PROMPT,
        stream_callback=tts.on_token,
        state_callback=update_hud_state
    )
    
    memory.llm = llm # inject LLM engine into memory
    
    stt = SpeechToText()
    intent = DualModelIntentClassifier(llm)
    
    # 5. Initialize Tool Modules
    vision = VisionEngine()
    email_handler = EmailHandler()
    whatsapp_handler = WhatsAppHandler()
    automation = AutomationEngine()
    code_engine = CodeEngine()
    scheduler = ReminderScheduler(tts.speak)
    web_search = WebSearchEngine()
    browser = BrowserController()
    image_gen = ImageGenerationEngine()
    game_monitor = GamingMonitor()
    iot_handler = IoTHandler()
    dashboard = JarvisHUD()
    conversation_memory = ConversationMemory(max_turns=config.MAX_HISTORY_TURNS, system_prompt=config.JARVIS_SYSTEM_PROMPT)
    def handle_ultraplan_hud(data):
        if isinstance(data, dict) and data.get("type") == "ultraplan_result":
            update_hud_transcript("jarvis", data.get("result", ""))
        elif isinstance(data, str):
            update_hud_state(data)
            
    ultraplan = UltraPlanCoordinator(llm, tts.speak, handle_ultraplan_hud)
    
    tools = build_tool_registry(
        automation, email_handler, whatsapp_handler, web_search, browser, vision, 
        memory, scheduler, image_gen, game_monitor, iot_handler, dashboard, get_weather, get_news, code_engine
    )
    
    react_agent = ReActAgent(llm, tools, memory)
    
    # Event flag for wake word
    wake_event = threading.Event()
    
    def on_wake_word_detected():
        wake_event.set()
        
    wake_detector = WakeWordDetector(on_wake_word_detected)
    
    # 6. Start Services
    wake_detector.start()
    
    # Start API server for HUD in background thread
    hud_server.start()
    
    def hitl_gate(action_name: str, fn: callable, *args) -> str:
        tts.speak(f"Sir, I'm about to {action_name.replace('_',' ')}. Please confirm.")
        update_hud_state("listening")
        confirm_text = stt.listen()
        update_hud_state("idle")
        if any(word in confirm_text.lower() for word in ["yes","confirm","proceed","do it"]):
            return fn(*args)
        return "Action cancelled, sir."

    SIMPLE_INTENTS = ["tell_time", "tell_date", "volume_up", "volume_down",
                      "mute", "take_screenshot", "open_app", "close_app",
                      "open_dashboard", "kill_dashboard", "clear_memory"]
                      
    def dispatch_intent(intent_name: str, entities: dict, raw_text: str) -> str:
        handlers = {
            "tell_time":        lambda: f"The time is {datetime.now().strftime('%I:%M %p')}, sir.",
            "tell_date":        lambda: f"Today is {datetime.now().strftime('%A, %B %d, %Y')}, sir.",
            "open_app":         lambda: automation.open_app(entities.get("app_name", "")),
            "close_app":        lambda: automation.close_app(entities.get("app_name", "")),
            "volume_up":        lambda: automation.volume_up(),
            "volume_down":      lambda: automation.volume_down(),
            "mute":             lambda: automation.mute_toggle(),
            "take_screenshot":  lambda: automation.take_screenshot(),
            "type_text":        lambda: automation.type_text(entities.get("text", "")),
            "clipboard_read":   lambda: automation.read_clipboard(),
            "clipboard_write":  lambda: automation.write_clipboard(entities.get("text", "")),
            "system_status":    lambda: automation.system_status(),
            "create_file":      lambda: automation.create_file(entities.get("file_path", ""), entities.get("text", "")),
            "read_file":        lambda: automation.read_file(entities.get("file_path", "")),
            "delete_file":      lambda: hitl_gate("delete_file", automation.delete_file, entities.get("file_path", "")),
            "move_file":        lambda: automation.move_file(entities.get("file_path", ""), entities.get("text", "")),
            "list_folder":      lambda: automation.list_folder(entities.get("file_path", "")),
            "send_email":       lambda: email_handler.compose_and_send(entities),
            "read_email":       lambda: email_handler.read_inbox(),
            "send_whatsapp":    lambda: whatsapp_handler.compose_and_send(entities),
            "web_search":       lambda: web_search.search_and_answer(entities.get("query", "")),
            "open_url":         lambda: browser.open_url(entities.get("url", "")),
            "open_incognito":   lambda: browser.open_incognito(entities.get("url", "")),
            "describe_screen":  lambda: vision.describe_screen(),
            "read_screen_text": lambda: vision.ocr_screen(),
            "describe_webcam":  lambda: vision.answer_about_webcam(raw_text),
            "search_memory":    lambda: memory.search(entities.get("query", "")),
            "ingest_document":  lambda: memory.ingest_document(entities.get("file_path", "")),
            "set_reminder":     lambda: scheduler.add_reminder(entities.get("time", ""), entities.get("reminder_msg", "")),
            "todays_schedule":  lambda: "No calendar handler implemented.", # Calendar excluded in imports based on prompt spec, fallback safely
            "add_calendar_event": lambda: "No calendar handler implemented.",
            "generate_image":   lambda: image_gen.generate_image(entities.get("text", "")),
            "open_gallery":     lambda: automation.open_app(str(config.IMAGES_DIR)),
            "open_game":        lambda: automation.open_app(entities.get("game_name", "")),
            "control_iot":      lambda: iot_handler.control(entities.get("iot_device", ""), entities.get("iot_action", "")),
            "open_dashboard":   lambda: dashboard.toggle(),
            "kill_dashboard":   lambda: dashboard.toggle(),
            "weather":          lambda: get_weather(entities.get("city", "Mumbai")),
            "get_news":         lambda: get_news(),
            "clear_memory":     lambda: (conversation_memory.clear(), "Memory cleared, sir.")[1],
        }
        handler = handlers.get(intent_name)
        if handler:
            try:
                return handler()
            except Exception as e:
                error_msg = f"I encountered an error with that, sir. {type(e).__name__}: {str(e)[:100]}"
                logging.error(f"Intent {intent_name} failed: {e}", exc_info=True)
                return error_msg
        else:
            return llm.generate(conversation_memory.get_messages(), stream=True)

    # Boot complete
    tts.speak("JARVIS online and ready, sir.")

    # Main Loop
    try:
        while True:
            # Check for typed commands first
            if not hud_server.command_queue.empty():
                raw_text = hud_server.command_queue.get()
                if raw_text == "__TOGGLE_MUTE__":
                    automation.mute_toggle()
                    continue
            else:
                # Wait for wake word
                wake_event.wait(timeout=0.1)
                if not wake_event.is_set():
                    continue
                
                wake_event.clear()
                update_hud_state("listening")
                
                raw_text = stt.listen()
                update_hud_state("idle")
                
                if not raw_text or len(raw_text.strip()) < 2:
                    tts.speak("I didn't catch that, sir.")
                    continue

            # Log and display
            print(f"\nYou: {raw_text}")
            update_hud_transcript("user", raw_text)

            # Memory context injection
            memory_context = memory.get_relevant_context(raw_text)

            # Intent classification
            classified = intent.classify(raw_text, conversation_memory.get_messages())
            intent_name = classified["intent"]
            entities = classified["entities"]

            # Build messages with memory context
            messages = conversation_memory.get_messages()
            if memory_context:
                messages.insert(1, {"role": "system", "content": memory_context})

            # COMPLEXITY ROUTING:
            complexity = llm.complexity_score(raw_text)

            if intent_name == "shutdown":
                tts.speak("Shutting down all systems. Goodbye, sir.")
                break

            elif intent_name == "chat" and complexity >= config.REACT_THRESHOLD:
                # Complex question — use full ReAct + CoT
                response = react_agent.run(raw_text, messages)
                tts.flush()
                conversation_memory.add_user_message(raw_text)
                conversation_memory.add_assistant_message(response)
                
            elif intent_name == "chat" and complexity < config.REACT_THRESHOLD:
                # Simple question — direct generate with streaming
                conversation_memory.add_user_message(raw_text)
                response = llm.generate(messages, stream=True, use_cot=config.USE_COT)
                tts.flush()
                conversation_memory.add_assistant_message(response)

            elif intent_name == "write_code":
                task = entities.get("text", raw_text)
                lang = entities.get("code_lang", "python")
                code = llm.generate_code(task, lang)
                clean_code = code_engine.extract_code(code) or code
                result = code_engine.execute_python(clean_code)
                if result.get("success"):
                    response = "I have executed the code successfully, sir."
                else:
                    response = "The code failed to execute, sir."
                tts.speak(response)

            elif complexity >= config.ULTRAPLAN_THRESHOLD and intent_name not in SIMPLE_INTENTS:
                # Complex multi-step task — UltraPlan background agents
                tts.speak(f"Starting background agents on that, sir. I'll update you.")
                ultraplan.execute_plan_async(raw_text)
                response = "Task assigned to background agents, sir."

            else:
                # All other specific intents — call the appropriate tool directly
                response = dispatch_intent(intent_name, entities, raw_text)
                if response:
                    tts.speak(response)

            # Post-turn operations (background threads)
            if response:
                update_hud_transcript("jarvis", response)
                threading.Thread(target=memory.extract_and_store_facts, args=(raw_text, response), daemon=True).start()

    except KeyboardInterrupt:
        print("\nShutting down by user interrupt...")
    finally:
        wake_detector.stop()
        tts.stop()
        hud_server.stop()

if __name__ == "__main__":
    main()
