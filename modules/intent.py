"""
modules/intent.py — JARVIS Intent Classifier
============================================
Uses Ollama (Mistral 7B at low temperature) to classify the user's
spoken command into one of 16 predefined intents and extract relevant
entities. Returns a structured dict compatible with main.py's dispatcher.
Falls back to "chat" intent if JSON parsing fails.
"""

import json
import logging
import re
from typing import Dict, Any

import ollama as ollama_client

import config
from modules.utils import robust_json_parse

logger = logging.getLogger(__name__)

# The complete list of supported intents
INTENTS = [
    "chat",             # general conversation — default
    "send_email",       # send an email
    "send_whatsapp",    # send a WhatsApp message
    "describe_screen",  # describe what's on screen
    "answer_screen",    # answer a question about the screen
    "describe_webcam",  # describe what the webcam sees
    "take_screenshot",  # take and save a screenshot
    "type_text",        # type something on screen
    "open_app",         # open an application
    "volume_up",        # increase system volume
    "volume_down",      # decrease system volume
    "mute",             # mute/unmute audio
    "tell_time",        # tell current time
    "tell_date",        # tell current date
    "clear_memory",     # clear conversation history
    "shutdown",         # shut down JARVIS
    "generate_image",   # generate an image from a description
    "speak_faster",     # increase TTS voice speed
    "speak_slower",     # decrease TTS voice speed
    "copy_clipboard",   # copy text to clipboard
    "paste_clipboard",  # paste text from clipboard
    "read_clipboard",   # read clipboard contents aloud
    "clear_clipboard",  # empty clipboard
    "create_file",      # create a new file
    "create_folder",    # create a new folder
    "move_file",        # move a file to a new path
    "rename_file",      # rename a file
    "delete_file",      # delete a file
    "delete_folder",    # delete a folder
    "list_folder",      # list contents of a folder
    "web_search",       # get quick answer from the web
    "open_search",      # open search results in a browser
    "system_status",    # report CPU, RAM, and battery info
    "extract_text",     # OCR text from screen
    "read_document",    # read PDF or Word document
    "show_gallery",     # show generated image gallery
    "enroll_voice",     # register user voice for authentication
    "read_emails",      # check and read recent emails
    "ultraplan",        # start deep thinking multi-agent session
    "get_weather",      # check current weather
    "set_reminder",     # schedule a voice reminder
    "get_news",         # fetch top news headlines
    "open_website",     # open a specific URL in browser
    "search_browser",   # search for something in browser
    "execute_powershell", # run a powershell command
    "start_routine",    # start a predefined routine
    "control_iot",      # control smart home devices
    "get_mood",         # detect user mood/emotion
    "switch_mode",      # switch between Work/Casual/Focus modes
    "system_report",    # report performance analytics
    "open_dashboard",   # activate the web visual dashboard/HUD
    "close_dashboard",  # deactivate the web visual dashboard/HUD
    "get_location",     # get current geographic location
    "api_cost",         # report Gemini API token usage and estimated USD cost
    "search_codebase",  # search the JARVIS codebase for a query
    "open_incognito",   # open a private/incognito browser window
    "mute_toggle",      # mute or unmute the microphone
    "use_mcp_tool",     # use a connected MCP tool (e.g., github, sqlite, fetch)
]

# Intents that require voice authentication/permission
PROTECTED_INTENTS = [
    "shutdown",
    "delete_file",
    "delete_folder",
    "move_file",
    "rename_file",
    "clear_memory",
    "send_email",
    "send_whatsapp",
    "execute_powershell",
]

# Prompt template for intent classification
_CLASSIFY_PROMPT = """You are an intent classifier for a voice assistant. Classify the user's message into EXACTLY one of these intents:

{intents}

Extract relevant entities from the message. Always return ONLY a valid JSON object with NO extra text, NO explanation, NO markdown, in EXACTLY this format:

{
  "intent": "<intent_name>",
  "entities": {
    "query": "<search query text>",
    "app_name": "<app to open>",
    ...
  }
}

EXAMPLES:
User: "Search for SpaceX on Google"
Response: {"intent": "web_search", "entities": {"query": "SpaceX"}}

User: "Open Chrome"
Response: {"intent": "open_app", "entities": {"app_name": "chrome"}}

User: "Tell me the weather in London"
Response: {"intent": "get_weather", "entities": {"location": "London"}}

User: "What are your features?"
Response: {"intent": "chat", "entities": {}}

User: "Open the dashboard"
Response: {"intent": "open_dashboard", "entities": {}}

User: "Turn off the visual interface"
Response: {"intent": "close_dashboard", "entities": {}}

User: "kill dashboard"
Response: {"intent": "close_dashboard", "entities": {}}

User: "Who are you?"
Response: {"intent": "chat", "entities": {}}

User: "Where am I right now?"
Response: {"intent": "get_location", "entities": {}}

User message: "{user_message}"
Recent Context: "{context}"

Respond with ONLY the JSON object: (Default to "chat" for general talk)"""


class IntentClassifier:
    """
    Classifies user voice commands into structured intents with entities.

    Uses Ollama with very low temperature (0.1) for deterministic,
    consistent classification. Falls back to the "chat" intent on any
    JSON parse error to ensure the system never fails catastrophically.
    """

    def __init__(self) -> None:
        """
        Initialize the intent classifier with Ollama client.
        """
        self._host = config.OLLAMA_HOST
        self._model = config.OLLAMA_MODEL
        self._backend = config.LLM_BACKEND
        self._api_key = config.GEMINI_API_KEY
        self.is_degraded = False # Track if we fell back to Ollama
        
        logger.info(
            f"IntentClassifier initialized — backend: {self._backend}, "
            f"model: {self._model if self._backend == 'ollama' else config.GEMINI_MODEL}"
        )

    def classify(self, text: str, context: str = "") -> Dict[str, Any]:
        """
        Classify user input text into an intent with extracted entities.

        Sends a structured prompt to Ollama requesting JSON output only.
        If the model returns non-JSON or malformed JSON, falls back to
        {intent: "chat", entities: {}}.

        Args:
            text (str): The user's spoken or typed command.
            context (str, optional): Recent conversation history to resolve pronouns/context.

        Returns:
            dict: A dict with keys:
                - "intent" (str): One of the INTENTS values.
                - "entities" (dict): Extracted entities with keys:
                  to, subject, body, to_name, text, app_name, question, count.
                  All keys always present; unused ones are empty strings or 1 for count.
        """
        fallback = {"intent": "chat", "entities": {}}

        if not text or not text.strip():
            return fallback
            
        # Fast heuristic bypass for common commands
        text_lower = text.strip().lower()
        if "open dashboard" in text_lower or "open the dashboard" in text_lower:
            return {"intent": "open_dashboard", "entities": {}}
        if "close dashboard" in text_lower or "close the dashboard" in text_lower:
            return {"intent": "close_dashboard", "entities": {}}

        intents_str = "\n".join(f"  - {intent}" for intent in INTENTS)
        ctx_str = context if context else "No recent context."
        prompt = _CLASSIFY_PROMPT.replace("{intents}", intents_str).replace("{user_message}", text.strip()).replace("{context}", ctx_str)

        try:
            raw = ""
            if self._backend == "gemini" and self._api_key:
                try:
                    from google import genai
                    client = genai.Client(api_key=self._api_key)
                    response = client.models.generate_content(
                        model=config.GEMINI_MODEL,
                        contents=prompt,
                        config={"temperature": 0.1}
                    )
                    raw = response.text.strip()
                except Exception as e:
                    err_msg = str(e).replace('\n', ' ')
                    logger.warning(f"Gemini intent classification failed ({err_msg[:150]}). Falling back to local Ollama.")
                    self.is_degraded = True
                    # Fallback for this call. Let's do fallback for this call.
                    
            if not raw:
                # Use Ollama as primary if config says so, or as fallback if Gemini failed
                try:
                    client = ollama_client.Client(host=self._host)
                    response = client.chat(
                        model=self._model,
                        messages=[{"role": "user", "content": prompt}],
                        options={
                            "temperature": 0.1,
                            "num_gpu": getattr(config, "OLLAMA_NUM_GPU", 0)
                        },
                    )
                    raw = response["message"]["content"].strip()
                except Exception as ollama_exc:
                    logger.warning(
                        f"Ollama intent classification also failed: {ollama_exc}. "
                        "Returning 'chat' fallback intent."
                    )
                    return fallback
            
            logger.debug(f"Intent classifier raw response: {raw}")

            # Extract JSON from the response (handles cases where model
            # adds a tiny bit of preamble despite instructions)
            json_match = re.search(r"\{.*\}", raw, re.DOTALL)
            if not json_match:
                logger.warning(
                    f"No JSON found in intent classifier response: {raw[:200]}"
                )
                return fallback

            parsed = robust_json_parse(json_match.group())

            # Validate and normalize the result
            intent = parsed.get("intent", "chat")
            if intent not in INTENTS:
                logger.warning(
                    f"Unknown intent '{intent}' returned — defaulting to 'chat'."
                )
                intent = "chat"

            entities = parsed.get("entities", {})
            # Ensure all expected entity keys are present
            full_entities = {
                "to": entities.get("to", ""),
                "subject": entities.get("subject", ""),
                "body": entities.get("body", ""),
                "to_name": entities.get("to_name", ""),
                "text": entities.get("text", ""),
                "app_name": entities.get("app_name", ""),
                "question": entities.get("question", ""),
                "prompt_text": entities.get("prompt_text", ""),
                "source_path": entities.get("source_path", ""),
                "destination_path": entities.get("destination_path", ""),
                "file_name": entities.get("file_name", ""),
                "folder_name": entities.get("folder_name", ""),
                "query": entities.get("query", ""),
                "file_path": entities.get("file_path", ""),
                "location": entities.get("location", ""),
                "time": entities.get("time", ""),
                "url": entities.get("url", ""),
                "command": entities.get("command", ""),
                "routine_name": entities.get("routine_name", ""),
                "iot_device": entities.get("iot_device", ""),
                "iot_action": entities.get("iot_action", ""),
                "mode": entities.get("mode", ""),
                "count": entities.get("count", 1)
            }

            result = {"intent": intent, "entities": full_entities}
            logger.info(
                f"Intent: '{intent}' | Entities: {full_entities}"
            )
            return result

        except json.JSONDecodeError as exc:
            logger.warning(f"JSON parse error in intent classifier: {exc}")
            return fallback
        except Exception as exc:
            logger.error(
                f"Intent classification failed: {exc}", exc_info=True
            )
            return fallback



