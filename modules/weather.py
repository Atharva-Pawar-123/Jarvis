"""
modules/weather.py — JARVIS Weather Module
==========================================
Fetches real-time weather information using the wttr.in service.
No API key required.
"""

import logging
import urllib.parse
import requests

logger = logging.getLogger(__name__)


def get_weather(location: str = "") -> str:
    """
    Fetch current weather for a specific location or the user's IP-based location.
    
    Args:
        location (str): City name or empty for auto-detect.
        
    Returns:
        str: A concise weather report.
    """
    try:
        # format=%C+%t (Condition + Temperature)
        # format=3 is "City: Condition Temp"
        encoded_location = urllib.parse.quote(location) if location else ""
        url = f"https://wttr.in/{encoded_location}?format=%C+and+%t"
        
        logger.info(f"Fetching weather for: {location or 'auto-detect'}")
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        weather_data = response.text.strip()
        
        if "Unknown location" in weather_data:
            return f"I'm sorry, sir. I couldn't find a location named {location}."
            
        location_display = location if location else "your current location"
        return f"The weather in {location_display} is {weather_data}, sir."

    except Exception as exc:
        logger.error(f"Weather fetch error: {exc}")
        return "I apologize, sir, but I'm having trouble connecting to the weather service."
