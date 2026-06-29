"""
modules/whatsapp_handler.py — JARVIS WhatsApp Messenger (pywhatkit)
====================================================================
Sends WhatsApp messages using pywhatkit which automates WhatsApp Web
via the default Chrome browser. WhatsApp Web must be open and logged
in for this to work. Normalizes phone number format and returns
JARVIS-style confirmation strings.

NOTE: WhatsApp Web must be logged in on the default Chrome browser.
pywhatkit opens a browser tab, types the message, and sends it.
The wait_time parameter gives the browser time to load before sending.
"""

import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)


class WhatsAppHandler:
    """
    WhatsApp message sender using pywhatkit.

    Requirements:
    - WhatsApp Web logged in on the system's default Chrome browser.
    - Internet connection.
    - Phone numbers in international format (e.g., +911234567890).
    """

    # Regex to validate international phone numbers
    _PHONE_PATTERN = re.compile(r"^\+\d{7,15}$")

    def _normalize_phone(self, phone: str) -> Optional[str]:
        """
        Normalize a phone number to international format with leading +.

        Accepts formats like:
          - +911234567890  (already correct)
          - 911234567890   (missing +)
          - +91-1234567890 (with separators)
          - 91 1234 567890 (with spaces)

        Args:
            phone (str): Raw phone number string from entities.

        Returns:
            str: Normalized phone number starting with '+', or None if invalid.
        """
        if not phone:
            return None

        # Remove spaces, dashes, parentheses
        cleaned = re.sub(r"[\s\-\(\)]", "", phone)

        # Add + prefix if missing
        if not cleaned.startswith("+"):
            cleaned = "+" + cleaned

        # Validate length and format
        if self._PHONE_PATTERN.match(cleaned):
            return cleaned

        logger.warning(f"Invalid phone number format: '{phone}' → '{cleaned}'")
        return None

    def send(self, phone_number: str, message: str) -> bool:
        """
        Send a WhatsApp message to the specified phone number.

        Opens WhatsApp Web in Chrome, navigates to the contact, types
        the message, and sends it. The tab is closed automatically after
        a 5-second delay.

        Args:
            phone_number (str): International format phone number (e.g. +911234567890).
            message (str): The message text to send.

        Returns:
            bool: True if the message was sent without errors, False otherwise.
        """
        import pywhatkit

        if not message or not message.strip():
            logger.error("WhatsApp send failed: message is empty.")
            return False

        normalized = self._normalize_phone(phone_number)
        if not normalized:
            logger.error(
                f"WhatsApp send failed: invalid phone number '{phone_number}'."
            )
            return False

        logger.info(f"Sending WhatsApp message to {normalized}...")

        try:
            pywhatkit.sendwhatmsg_instantly(
                phone_no=normalized,
                message=message.strip(),
                wait_time=15,       # seconds to wait for WhatsApp Web to load
                tab_close=True,     # close the tab after sending
                close_time=5,       # seconds before closing tab
            )
            logger.info(f"WhatsApp message sent to {normalized}.")
            return True

        except Exception as exc:
            logger.error(
                f"WhatsApp send to {normalized} failed: {exc}", exc_info=True
            )
            return False

    def compose_and_send(self, entities: dict) -> str:
        """
        Extract WhatsApp fields from intent entities and send the message.

        Args:
            entities (dict): Entity dict with keys 'to' (phone number) and
                'body' (message text).

        Returns:
            str: JARVIS-style confirmation or error message.
        """
        phone = entities.get("to", "").strip()
        message = entities.get("body", "").strip()
        to_name = entities.get("to_name", "").strip()

        if not phone:
            return (
                "I don't have a phone number to send to, sir. "
                "Please specify the number in international format."
            )

        if not message:
            return "I don't have any message content, sir. Please tell me what to write."

        normalized = self._normalize_phone(phone)
        if not normalized:
            return (
                f"The phone number '{phone}' doesn't look right, sir. "
                "Please use international format, for example: plus 91 followed by the number."
            )

        success = self.send(phone_number=normalized, message=message)

        if success:
            recipient_display = to_name if to_name else normalized
            return f"WhatsApp message sent to {recipient_display}, sir."
        else:
            return (
                "I was unable to send the WhatsApp message, sir. "
                "Please ensure WhatsApp Web is logged in on Chrome and you have an internet connection."
            )
