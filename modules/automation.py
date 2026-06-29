"""
modules/automation.py — JARVIS Screen Automation Engine
========================================================
Provides system automation: typing text via clipboard, launching
applications, taking screenshots, and controlling system volume.
Uses pyautogui for GUI interaction, ctypes for Windows API calls,
subprocess for app launching, and pyperclip for clipboard operations.
"""

import ctypes
import datetime
import logging
import os
import psutil
import shutil
import time
from pathlib import Path
from typing import Optional

import pyautogui
import pyperclip

import config

logger = logging.getLogger(__name__)

# PyAutoGUI safety settings
pyautogui.PAUSE = 0.1       # 100ms pause between actions
pyautogui.FAILSAFE = True   # Move mouse to top-left corner to abort

# Windows virtual key codes for media/volume keys
VK_VOLUME_UP = 0xAF
VK_VOLUME_DOWN = 0xAE
VK_VOLUME_MUTE = 0xAD
KEYEVENTF_KEYUP = 0x0002


class AutomationEngine:
    """
    Windows screen and system automation.

    Provides text typing, app launching, screenshots, and volume control
    using pyautogui, ctypes, subprocess, and pyperclip.
    """

    # Map of common app aliases to their executable names or full paths
    _APP_MAP = {
        "notepad": "notepad.exe",
        "note": "notepad.exe",
        "calculator": "calc.exe",
        "calc": "calc.exe",
        "chrome": r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        "google chrome": r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        "firefox": r"C:\Program Files\Mozilla Firefox\firefox.exe",
        "mozilla firefox": r"C:\Program Files\Mozilla Firefox\firefox.exe",
        "edge": r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        "microsoft edge": r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        "explorer": "explorer.exe",
        "file explorer": "explorer.exe",
        "files": "explorer.exe",
        "cmd": "cmd.exe",
        "command prompt": "cmd.exe",
        "powershell": "powershell.exe",
        "paint": "mspaint.exe",
        "mspaint": "mspaint.exe",
        "wordpad": "wordpad.exe",
        "word pad": "wordpad.exe",
        "task manager": "taskmgr.exe",
        "taskmgr": "taskmgr.exe",
        "control panel": "control.exe",
        "snipping tool": "SnippingTool.exe",
    }

    def type_text(self, text: str) -> str:
        """
        Type the specified text at the current cursor position.

        Uses clipboard paste (Ctrl+V) rather than keystroke simulation
        to handle all characters correctly, including Unicode.

        Args:
            text (str): The text to type/paste at the current cursor location.

        Returns:
            str: Confirmation message for TTS output.
        """
        try:
            pyperclip.copy(text)
            time.sleep(0.2)  # Allow clipboard to update
            pyautogui.hotkey("ctrl", "v")
            log_preview = text[:50] + ("..." if len(text) > 50 else "")
            logger.info(f"Typed text via clipboard: '{log_preview}'")
            return "Text typed, sir."
        except Exception as exc:
            logger.error(f"type_text failed: {exc}", exc_info=True)
            return f"I was unable to type that text, sir. {exc}"

    def open_app(self, app_name: str) -> str:
        """
        Open an application by name.

        Maps common app names (case-insensitive, partial match) to their
        executable paths. Falls back to using the app_name directly as a
        command if no mapping is found.

        Args:
            app_name (str): The application name to open (e.g. "Chrome", "Notepad").

        Returns:
            str: Confirmation or error message for TTS output.
        """
        if not app_name or not app_name.strip():
            return "Please tell me which application to open, sir."

        app_lower = app_name.strip().lower()

        # Look for a direct or partial match in the app map
        executable = None
        for key, path in self._APP_MAP.items():
            if app_lower in key or key in app_lower:
                executable = path
                break

        # Fall back to using the name as-is
        if not executable:
            executable = app_name.strip()
            logger.info(
                f"App '{app_name}' not in known map — trying directly: '{executable}'"
            )

        try:
            os.startfile(executable)
            logger.info(f"Opened app: {executable}")
            return f"Opening {app_name}, sir."
        except FileNotFoundError:
            logger.error(f"App not found: {executable}")
            return f"I couldn't find {app_name}, sir. Please check the application is installed."
        except Exception as exc:
            logger.error(f"open_app failed for '{app_name}': {exc}", exc_info=True)
            return f"I was unable to open {app_name}, sir."

    def take_screenshot(self, save_path: Optional[str] = None) -> str:
        """
        Take a screenshot and save it to disk.

        Args:
            save_path (str, optional): Full file path to save the screenshot.
                Defaults to D:/JARVIS/logs/screenshot_YYYYMMDD_HHMMSS.png.

        Returns:
            str: The absolute path where the screenshot was saved.
        """
        if save_path is None:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            save_path = str(
                Path(config.BASE_DIR) / "logs" / f"screenshot_{timestamp}.png"
            )

        try:
            screenshot = pyautogui.screenshot()
            screenshot.save(save_path)
            logger.info(f"Screenshot saved to: {save_path}")
            return save_path
        except Exception as exc:
            logger.error(f"Screenshot failed: {exc}", exc_info=True)
            return f"Screenshot failed: {exc}"

    def _press_key(self, vk_code: int, presses: int = 1) -> None:
        """
        Press a Windows virtual key using ctypes keybd_event.

        Args:
            vk_code (int): Windows Virtual Key code.
            presses (int): Number of times to press the key.
        """
        for _ in range(presses):
            ctypes.windll.user32.keybd_event(vk_code, 0, 0, 0)
            time.sleep(0.05)
            ctypes.windll.user32.keybd_event(vk_code, 0, KEYEVENTF_KEYUP, 0)
            time.sleep(0.05)

    def volume_up(self, amount: int = 10) -> str:
        """
        Increase the system volume by pressing the Volume Up key.

        Args:
            amount (int): Number of volume key presses (each ~2% on most systems).
                Defaults to 10 presses.

        Returns:
            str: Confirmation message for TTS output.
        """
        try:
            self._press_key(VK_VOLUME_UP, presses=amount)
            logger.info(f"Volume increased by {amount} presses.")
            return "Volume increased, sir."
        except Exception as exc:
            logger.error(f"volume_up failed: {exc}", exc_info=True)
            return "I was unable to adjust the volume, sir."

    def volume_down(self, amount: int = 10) -> str:
        """
        Decrease the system volume by pressing the Volume Down key.

        Args:
            amount (int): Number of volume key presses. Defaults to 10 presses.

        Returns:
            str: Confirmation message for TTS output.
        """
        try:
            self._press_key(VK_VOLUME_DOWN, presses=amount)
            logger.info(f"Volume decreased by {amount} presses.")
            return "Volume decreased, sir."
        except Exception as exc:
            logger.error(f"volume_down failed: {exc}", exc_info=True)
            return "I was unable to adjust the volume, sir."

    def mute_toggle(self) -> str:
        """
        Toggle the system mute state by pressing the Mute key.

        Returns:
            str: Confirmation message for TTS output.
        """
        try:
            self._press_key(VK_VOLUME_MUTE, presses=1)
            logger.info("Mute toggled.")
            return "Audio mute toggled, sir."
        except Exception as exc:
            logger.error(f"mute_toggle failed: {exc}", exc_info=True)
            return "I was unable to toggle mute, sir."

    # -----------------------------------------------------------------------
    # Clipboard Operations
    # -----------------------------------------------------------------------
    def copy_clipboard(self, text: str) -> str:
        try:
            pyperclip.copy(text)
            return "Copied to clipboard, sir."
        except Exception as exc:
            logger.error(f"copy_clipboard failed: {exc}")
            return "I was unable to copy to the clipboard, sir."

    def paste_clipboard(self) -> str:
        try:
            return pyperclip.paste()
        except Exception as exc:
            logger.error(f"paste_clipboard failed: {exc}")
            return "I was unable to read the clipboard, sir."

    def clear_clipboard(self) -> str:
        try:
            pyperclip.copy("")
            return "Clipboard cleared, sir."
        except Exception as exc:
            logger.error(f"clear_clipboard failed: {exc}")
            return "I was unable to clear the clipboard, sir."

    # -----------------------------------------------------------------------
    # File Operations
    # -----------------------------------------------------------------------
    def create_file(self, path: str) -> str:
        try:
            p = Path(path)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.touch(exist_ok=True)
            return f"File created at {p.name}, sir."
        except Exception as exc:
            logger.error(f"create_file failed: {exc}")
            return "I could not create the file, sir."

    def create_folder(self, path: str) -> str:
        try:
            p = Path(path)
            p.mkdir(parents=True, exist_ok=True)
            return f"Folder {p.name} created, sir."
        except Exception as exc:
            logger.error(f"create_folder failed: {exc}")
            return "I could not create the folder, sir."

    def move_file(self, source: str, dest: str) -> str:
        try:
            shutil.move(source, dest)
            return f"Moved successfully to {Path(dest).name}, sir."
        except Exception as exc:
            logger.error(f"move_file failed: {exc}")
            return "I could not move the item, sir."

    def rename_file(self, source: str, new_name: str) -> str:
        try:
            p = Path(source)
            new_path = p.parent / new_name
            p.rename(new_path)
            return f"Renamed to {new_name}, sir."
        except Exception as exc:
            logger.error(f"rename_file failed: {exc}")
            return "I could not rename the item, sir."

    def delete_item(self, path: str) -> str:
        try:
            p = Path(path)
            if p.is_file():
                p.unlink()
            elif p.is_dir():
                shutil.rmtree(p)
            return f"Deleted {p.name}, sir."
        except Exception as exc:
            logger.error(f"delete_item failed: {exc}")
            return "I could not delete the item, sir."

    def list_folder(self, path: str) -> str:
        try:
            p = Path(path)
            if not p.is_dir():
                return "That path is not a valid folder, sir."
            items = list(p.iterdir())
            names = [i.name for i in items[:10]]
            res = f"The folder contains: {', '.join(names)}."
            if len(items) > 10:
                res += f" And {len(items) - 10} more items."
            return res
        except Exception as exc:
            logger.error(f"list_folder failed: {exc}")
            return "I could not read the folder contents, sir."

    def get_system_status(self) -> str:
        """
        Collect and report CPU, RAM, and Battery status.
        """
        try:
            cpu = psutil.cpu_percent(interval=0.5)
            ram = psutil.virtual_memory().percent
            battery = psutil.sensors_battery()
            
            status = f"System report, sir. CPU usage is at {cpu} percent. Memory is at {ram} percent."
            
            if battery:
                status += f" Battery is at {battery.percent} percent and {'charging' if battery.power_plugged else 'discharging'}."
            
            return status
        except Exception as exc:
            logger.error(f"get_system_status failed: {exc}")
            return "I was unable to retrieve the system status, sir."

    def get_active_window(self) -> str:
        """
        Get the title of the currently active window.
        """
        try:
            # Using pyautogui to get the active window title
            window = pyautogui.getActiveWindow()
            if window:
                return f"The active window is {window.title}, sir."
            return "I couldn't identify the active window, sir."
        except Exception as exc:
            logger.error(f"get_active_window failed: {exc}")
            return "I failed to retrieve the window information, sir."
