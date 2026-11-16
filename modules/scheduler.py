"""
modules/scheduler.py — JARVIS Reminder Scheduler
================================================
Manages time-based reminders in a background thread.
Uses dateutil for flexible natural language time parsing.
"""

import json
import logging
import re
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Callable

from dateutil import parser

logger = logging.getLogger(__name__)


class ReminderScheduler:
    """
    Background scheduler that triggers TTS reminders when due.
    """

    def __init__(self, tts_callback: Callable[[str], None], storage_path: str = "data/reminders.json") -> None:
        self.tts_callback = tts_callback
        self.storage_path = Path(storage_path)
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        
        self.reminders: List[dict] = self._load_reminders()
        self.running = True
        self._lock = threading.Lock()
        
        # Start background check thread
        self.thread = threading.Thread(target=self._check_loop, daemon=True)
        self.thread.start()
        logger.info("Reminder scheduler started.")

    def _load_reminders(self) -> List[dict]:
        if self.storage_path.exists():
            try:
                return json.loads(self.storage_path.read_text())
            except Exception as exc:
                logger.error(f"Failed to load reminders: {exc}")
                return []
        return []

    def _save_reminders(self) -> None:
        try:
            with self._lock:
                self.storage_path.write_text(json.dumps(self.reminders, indent=2))
        except Exception as exc:
            logger.error(f"Failed to save reminders: {exc}")

    def add_reminder(self, time_str: str, task: str) -> str:
        """
        Parse a time string and add a reminder to the list.
        """
        try:
            # Handle relative times like "in 10 minutes" or "in 1 hour and 30 minutes"
            # Use word-boundary match to avoid false positives ("interesting", "information")
            if re.search(r'\bin\b', time_str.lower()):
                now = datetime.now()
                minutes = 0
                hours = 0
                
                # Simple extraction for hours
                hr_match = re.search(r'(\d+)\s*hour', time_str.lower())
                if hr_match:
                    hours = int(hr_match.group(1))
                elif "an hour" in time_str.lower():
                    hours = 1
                    
                # Simple extraction for minutes
                min_match = re.search(r'(\d+)\s*minute', time_str.lower())
                if min_match:
                    minutes = int(min_match.group(1))
                elif "a minute" in time_str.lower():
                    minutes = 1
                
                # Fallback if no keywords found but digits exist
                if not hours and not minutes:
                    digits = ''.join(filter(str.isdigit, time_str))
                    minutes = int(digits) if digits else 1
                
                due_time = now + timedelta(hours=hours, minutes=minutes)
            else:
                # Absolute time parsing (e.g. "3:30 PM")
                due_time = parser.parse(time_str)
                # If parsed time is in the past, assume it's for tomorrow
                if due_time < datetime.now():
                    due_time += timedelta(days=1)

            import uuid
            reminder = {
                "id": uuid.uuid4().hex[:12],
                "due_at": due_time.isoformat(),
                "task": task,
                "triggered": False
            }

            with self._lock:
                self.reminders.append(reminder)
            self._save_reminders()

            friendly_time = due_time.strftime("%I:%M %p")
            return f"Reminder set for {friendly_time}: {task}, sir."

        except Exception as exc:
            logger.error(f"Failed to add reminder: {exc}")
            return "I'm sorry, sir. I couldn't understand that time format."

    def _check_loop(self) -> None:
        """Background thread that checks for due reminders every 30 seconds."""
        while self.running:
            try:
                now = datetime.now()
                to_trigger = []
                
                with self._lock:
                    for r in self.reminders:
                        if not r["triggered"] and now >= datetime.fromisoformat(r["due_at"]):
                            r["triggered"] = True
                            to_trigger.append(r["task"])

                if to_trigger:
                    for task in to_trigger:
                        logger.info(f"Triggering reminder: {task}")
                        self.tts_callback(f"Sir, I have a reminder for you: {task}")

                    # Clean up triggered reminders
                    with self._lock:
                        self.reminders = [r for r in self.reminders if not r["triggered"]]
                    self._save_reminders()

            except Exception as exc:
                logger.error(f"Error in scheduler loop: {exc}")
            
            time.sleep(30)

    def stop(self) -> None:
        self.running = False
