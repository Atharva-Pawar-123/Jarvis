import json
import logging
import time

class DualModelIntentClassifier:
    """
    Routes queries to fast model for clear intents, or primary model for ambiguous ones.
    Must complete fast classification in < 200ms.
    """
    
    INTENTS = [
        "chat", "clear_memory", "shutdown",
        "open_app", "close_app", "volume_up", "volume_down", "mute", 
        "take_screenshot", "type_text", "clipboard_read", "clipboard_write", "system_status",
        "create_file", "read_file", "edit_file", "delete_file", "move_file", "list_folder", 
        "write_code", "run_file", "fix_code",
        "send_email", "read_email", "send_whatsapp", "send_telegram",
        "web_search", "open_url", "open_incognito", "browser_automate",
        "describe_screen", "read_screen_text", "describe_webcam",
        "search_memory", "search_documents", "ingest_document",
        "set_reminder", "todays_schedule", "add_calendar_event",
        "generate_image", "open_gallery", "play_music", "open_game",
        "control_iot",
        "complex_task",
        "open_dashboard", "kill_dashboard", "tell_time", "tell_date", "weather", "get_news"
    ]
    
    def __init__(self, llm_engine):
        self.llm = llm_engine
        self.cache = {}
        
        # System prompt under 200 tokens for maximum speed
        intent_list_str = ", ".join(self.INTENTS)
        self.system_prompt = (
            "Classify the user's request. Return ONLY a JSON object with keys "
            f"'intent' (one of: {intent_list_str}) and 'entities' "
            "(keys: text, to, subject, app_name, file_path, url, query, code_lang, game_name, "
            "iot_device, iot_action, time, date, city, reminder_msg, duration, volume_level, song, topic, confirm). "
            "No markdown. No explanation. Pure JSON only."
        )

    def classify(self, user_text: str, conversation_history: list = None) -> dict:
        # Step 1: Cache check (3 min expiration)
        now = time.time()
        if user_text in self.cache:
            entry, timestamp = self.cache[user_text]
            if now - timestamp < 180:
                return entry
                
        messages = [{"role": "system", "content": self.system_prompt}, {"role": "user", "content": user_text}]
        
        # Step 2: Try fast model
        try:
            # Note: temperature is set in LLMEngine options or we just rely on fast deterministic
            res = self.llm._generate_blocking(messages, self.llm.FAST_MODEL)
            result = self._parse_json(res)
        except Exception as e:
            logging.warning(f"Fast intent classification failed/timed out: {e}. Falling back to Primary.")
            result = None
            
        # Step 3: Fallback to primary
        if not result:
            try:
                res = self.llm._generate_blocking(messages, self.llm.PRIMARY_MODEL)
                result = self._parse_json(res)
            except Exception as e:
                logging.error(f"Primary classification also failed: {e}")
                result = {"intent": "chat", "entities": {}}
                
        # Step 4: Validate and Fill Schema
        if not result or not isinstance(result, dict) or "intent" not in result:
            result = {"intent": "chat", "entities": {}}
            
        if result["intent"] not in self.INTENTS:
            result["intent"] = "chat"
            
        entities = result.get("entities", {})
        if not isinstance(entities, dict):
            entities = {}
            
        # Ensure all keys exist with empty strings if missing
        schema_keys = ["text", "to", "subject", "app_name", "file_path", "url", "query", 
                       "code_lang", "game_name", "iot_device", "iot_action", "time", "date", 
                       "city", "reminder_msg", "duration", "volume_level", "song", "topic", "confirm"]
                       
        for key in schema_keys:
            if key not in entities or entities[key] is None:
                entities[key] = ""
                
        result["entities"] = entities
        
        # Step 5: Cache
        self.cache[user_text] = (result, now)
        
        return result

    def _parse_json(self, text: str) -> dict:
        """Robustly extract and parse JSON from the LLM output."""
        # Strip markdown fences if present
        text = text.strip()
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
            
        text = text.strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # Fallback regex extraction if it wrote prose before JSON
            import re
            match = re.search(r'\{.*\}', text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(0))
                except json.JSONDecodeError:
                    return None
            return None
