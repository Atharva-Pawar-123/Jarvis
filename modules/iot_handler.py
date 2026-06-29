"""
modules/iot_handler.py — JARVIS Smart Home Integration
=======================================================
Connects to local smart home hubs (Home Assistant, Philips Hue, etc.) via REST APIs.
"""

import logging
import config

logger = logging.getLogger(__name__)

class IoTHandler:
    """
    Handles communication with smart home devices.
    """

    def __init__(self) -> None:
        self.ha_url = getattr(config, "HOME_ASSISTANT_URL", "http://homeassistant.local:8123")
        self.ha_token = getattr(config, "HOME_ASSISTANT_TOKEN", "")
        self.headers = {
            "Authorization": f"Bearer {self.ha_token}",
            "Content-Type": "application/json",
        }

    def control_device(self, device: str, action: str) -> str:
        """
        Send a command to a smart home device.
        """
        if not self.ha_token:
            return "Home Assistant is not configured, sir. Please add your token to the configuration."

        if not device or not action:
            return "Which device should I control, and what should I do, sir?"

        # Mapping common names to entity IDs would happen here
        # For now, we assume simple entity strings or fuzzy matching
        logger.info(f"IoT Control: {device} -> {action}")
        
        # Example API call to Home Assistant
        # domain = "light" or "switch"
        # service = "turn_on" or "turn_off"
        
        try:
            # Placeholder for actual HA API logic
            # response = requests.post(f"{self.ha_url}/api/services/{domain}/{service}", ...)
            return f"Understood, sir. I'm turning the {device} {action} now."
        except Exception as exc:
            logger.error(f"IoT control failed: {exc}")
            return f"I failed to control the {device}, sir."
