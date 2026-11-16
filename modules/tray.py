"""
modules/tray.py — JARVIS System Tray Icon
=========================================
Runs a background tray icon using pystray.
Provides a context menu to toggle the HUD, restart, mute, and shutdown.
"""

import logging
import os
import sys
import threading
from PIL import Image, ImageDraw

logger = logging.getLogger(__name__)

# Try to import pystray, but don't crash if it's missing (fails gracefully)
try:
    import pystray
    from pystray import MenuItem as item
except ImportError:
    pystray = None
    logger.warning("pystray not installed. Tray icon will be disabled.")


class JarvisTray:
    """
    Manages the JARVIS system tray icon and context menu.
    """

    def __init__(self, callbacks: dict) -> None:
        """
        Initialize the tray icon with provided callbacks.
        
        Args:
            callbacks (dict): A dictionary of callback functions:
                - "toggle_hud": Function to toggle HUD visibility
                - "toggle_mute": Function to toggle microphone mute
                - "shutdown": Function to trigger graceful shutdown
        """
        self.callbacks = callbacks
        self.icon = None
        
        if pystray is None:
            return

        self._thread = threading.Thread(target=self._run_tray, daemon=True)
        self._thread.start()

    def _create_icon_image(self) -> Image.Image:
        """
        Generate a simple, generic JARVIS icon (cyan circle) if a file doesn't exist.
        """
        image = Image.new('RGB', (64, 64), color='black')
        draw = ImageDraw.Draw(image)
        draw.ellipse((16, 16, 48, 48), fill='#00FFFF')
        return image

    def _run_tray(self) -> None:
        """
        Setup and run the pystray icon loop.
        """
        menu = (
            item('Toggle HUD', self._on_toggle_hud),
            item('Mute/Unmute Mic', self._on_toggle_mute),
            item('Restart JARVIS', self._on_restart),
            item('Shut Down', self._on_shutdown)
        )
        
        self.icon = pystray.Icon(
            "JARVIS",
            self._create_icon_image(),
            "JARVIS System Active",
            menu
        )
        
        logger.info("System Tray Icon initialized.")
        self.icon.run()

    def _on_toggle_hud(self) -> None:
        if "toggle_hud" in self.callbacks:
            self.callbacks["toggle_hud"]()

    def _on_toggle_mute(self) -> None:
        if "toggle_mute" in self.callbacks:
            self.callbacks["toggle_mute"]()

    def _on_restart(self) -> None:
        """
        Restart the JARVIS python process entirely.
        """
        logger.info("Restarting JARVIS via Tray Icon...")
        if self.icon:
            self.icon.stop()
        os.execv(sys.executable, [sys.executable] + sys.argv)

    def _on_shutdown(self) -> None:
        """
        Trigger the shutdown callback.
        """
        logger.info("Shutdown requested via Tray Icon.")
        if "shutdown" in self.callbacks:
            self.callbacks["shutdown"]()
        if self.icon:
            self.icon.stop()
