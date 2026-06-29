"""
modules/location.py — JARVIS Geolocation Module
===============================================
Provides IP-based geolocation to determine the user's current 
coordinates and city. This is used to sync the HUD map.
"""

import logging
import requests

logger = logging.getLogger(__name__)

def get_current_location():
    """
    Get the user's current location based on their public IP.
    
    Returns:
        dict: {
            "lat": float,
            "lon": float,
            "city": str,
            "country": str,
            "status": "success" or "fail"
        }
    """
    try:
        logger.info("Detecting current location via IP...")
        # Using ip-api.com (free for non-commercial use, no key needed)
        response = requests.get("http://ip-api.com/json/", timeout=5)
        response.raise_for_status()
        data = response.json()
        
        if data.get("status") == "success":
            logger.info(f"Location detected: {data.get('city')}, {data.get('country')}")
            return {
                "lat": data.get("lat"),
                "lon": data.get("lon"),
                "city": data.get("city"),
                "country": data.get("country"),
                "status": "success"
            }
        else:
            logger.warning("IP-based location detection failed.")
            return {"status": "fail", "message": "API returned failure status"}
            
    except Exception as exc:
        logger.error(f"Location detection error: {exc}")
        return {"status": "fail", "message": str(exc)}
