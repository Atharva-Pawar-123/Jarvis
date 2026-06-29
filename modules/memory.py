"""
modules/memory.py — JARVIS Conversation Memory Manager
=======================================================
Maintains a sliding-window conversation history for the LLM context.
The system prompt is always prepended. History is trimmed to max_turns * 2
messages (each turn = 1 user + 1 assistant message).
"""

import datetime
import logging
from pathlib import Path
from typing import List, Dict
import config

logger = logging.getLogger(__name__)


class ConversationMemory:
    """
    Manages conversation history for the JARVIS LLM context window.

    Attributes:
        max_turns (int): Maximum number of conversation turns to retain.
        system_prompt (str): The JARVIS personality/system prompt.
        _history (list): Internal list of message dicts (role + content).
    """

    def __init__(self, max_turns: int, system_prompt: str) -> None:
        """
        Initialize the conversation memory.

        Args:
            max_turns (int): Maximum number of user/assistant turn pairs to keep.
            system_prompt (str): The system prompt defining JARVIS's personality.
        """
        self.max_turns = max_turns
        self.system_prompt = system_prompt
        self._history: List[Dict[str, str]] = []
        
        # Setup session log file
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        log_dir = Path(config.BASE_DIR) / "logs" / "conversations"
        log_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = log_dir / f"session_{timestamp}.txt"
        
        logger.info(f"ConversationMemory initialized with max_turns={max_turns}.")
        self._log_to_file("--- SESSION STARTED ---")

    def update_system_prompt(self, new_prompt: str) -> None:
        """
        Update the system prompt (e.g. to inject retrieved context).
        """
        self.system_prompt = new_prompt
        logger.debug("System prompt updated with new context.")

    def add_user_message(self, text: str) -> None:
        """
        Append a user message to the conversation history.

        Args:
            text (str): The user's spoken/typed message.
        """
        self._history.append({"role": "user", "content": text})
        preview = text[:80] + ("..." if len(text) > 80 else "")
        logger.debug(f"User message added to memory: {preview}")
        self._log_to_file(f"YOU: {text}")
        self._trim()

    def add_message(self, role: str, content: str, name: str = None) -> None:
        """
        Append a generic message (e.g., tool/function call/result) to the history.
        """
        msg = {"role": role, "content": content}
        if name:
            msg["name"] = name
        self._history.append(msg)
        preview = content[:80] + ("..." if len(content) > 80 else "")
        logger.debug(f"Generic message ({role}) added to memory: {preview}")
        
        # Don't strictly log raw tool payloads to the conversational file unless needed
        if role == "tool":
            self._log_to_file(f"[TOOL {name}]: {content[:100]}...")
        else:
            self._log_to_file(f"{role.upper()}: {content}")
        self._trim()

    def add_assistant_message(self, text: str) -> None:
        """
        Append an assistant (JARVIS) message to the conversation history.

        Args:
            text (str): JARVIS's response text.
        """
        self._history.append({"role": "assistant", "content": text})
        preview = text[:80] + ("..." if len(text) > 80 else "")
        logger.debug(f"Assistant message added to memory: {preview}")
        self._log_to_file(f"JARVIS: {text}")
        self._trim()

    def get_messages(self) -> List[Dict[str, str]]:
        """
        Build and return the full message list for the Ollama API.

        The system prompt is always first, followed by the trimmed history.

        Returns:
            list[dict]: A list of message dicts with 'role' and 'content' keys.
        """
        messages = [{"role": "system", "content": self.system_prompt}]
        messages.extend(self._history)
        return messages

    def clear(self) -> None:
        """
        Clear all conversation history while keeping the system prompt intact.
        """
        self._history.clear()
        logger.info("Conversation memory cleared.")

    def _trim(self) -> None:
        """
        Trim the history to the last max_turns * 2 messages.
        Each turn consists of one user message and one assistant message.
        """
        max_messages = self.max_turns * 2
        if len(self._history) > max_messages:
            removed = len(self._history) - max_messages
            self._history = self._history[-max_messages:]
            logger.debug(f"Memory trimmed: removed {removed} old messages.")

    def _log_to_file(self, message: str) -> None:
        """
        Append a message to the persistent session log file with a timestamp.
        """
        try:
            timestamp = datetime.datetime.now().strftime("%H:%M:%S")
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(f"[{timestamp}] {message}\n")
        except Exception as exc:
            logger.error(f"Failed to write to conversation log: {exc}")

    def __len__(self) -> int:
        """
        Return the number of conversation turns stored (not counting system prompt).

        Returns:
            int: Number of turns (each turn = 1 user + 1 assistant message pair).
        """
        return len(self._history) // 2
