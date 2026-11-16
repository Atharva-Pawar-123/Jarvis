"""
modules/computer_use.py — Windows Accessibility & Interactive Computer Use
===========================================================================
Replaces blind PyAutoGUI screen clicks with native Windows UI Automation (win32gui / win32con)
and headless browser automation (Playwright).
Allows JARVIS to:
- Enumerate top-level window handles and active applications.
- Focus and manipulate target windows directly.
- Inspect window titles, bounds, and hierarchy.
- Perform deterministic browser research via Playwright without mouse hijacking.
"""

import logging
import asyncio
from typing import Dict, Any, List, Optional
import win32gui
import win32con
import win32process

logger = logging.getLogger(__name__)


class WindowsComputerUse:
    """Provides structured desktop inspection and window interaction."""

    def __init__(self):
        pass

    def list_open_windows(self) -> List[Dict[str, Any]]:
        """Enumerates visible desktop windows with handles and titles."""
        windows = []

        try:
            def enum_cb(hwnd, extra):
                try:
                    if win32gui.IsWindowVisible(hwnd) and win32gui.GetWindowText(hwnd):
                        title = win32gui.GetWindowText(hwnd)
                        rect = win32gui.GetWindowRect(hwnd)
                        width = rect[2] - rect[0]
                        height = rect[3] - rect[1]
                        if width > 50 and height > 50:
                            _, pid = win32process.GetWindowThreadProcessId(hwnd)
                            windows.append({
                                "hwnd": hwnd,
                                "title": title,
                                "pid": pid,
                                "bounds": {"x": rect[0], "y": rect[1], "width": width, "height": height}
                            })
                except Exception:
                    pass

            win32gui.EnumWindows(enum_cb, None)
        except Exception as e:
            logger.warning(f"Window enumeration unavailable in session: {e}")

        return windows

    def focus_window(self, title_query: str) -> bool:
        """Finds a window by partial title match and brings it to the foreground."""
        matches = [w for w in self.list_open_windows() if title_query.lower() in w["title"].lower()]
        if not matches:
            return False

        hwnd = matches[0]["hwnd"]
        try:
            # If minimized, restore it
            if win32gui.IsIconic(hwnd):
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            win32gui.SetForegroundWindow(hwnd)
            return True
        except Exception as e:
            logger.warning(f"Could not focus window {hwnd}: {e}")
            return False

    def get_active_window(self) -> Dict[str, Any]:
        """Gets title and metadata of the currently focused window."""
        hwnd = win32gui.GetForegroundWindow()
        if not hwnd:
            return {"title": "None", "hwnd": 0}
        title = win32gui.GetWindowText(hwnd)
        rect = win32gui.GetWindowRect(hwnd)
        return {
            "title": title,
            "hwnd": hwnd,
            "bounds": {"x": rect[0], "y": rect[1], "width": rect[2] - rect[0], "height": rect[3] - rect[1]}
        }


class PlaywrightBrowserAgent:
    """Deterministic browser agent using Playwright without mouse hijacking."""

    def __init__(self):
        self._browser = None

    async def fetch_page_content(self, url: str) -> str:
        """Navigates to URL headlessly and returns cleaned readable text."""
        try:
            from playwright.async_api import async_playwright
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                await page.goto(url, timeout=20000)
                # Extract text
                content = await page.inner_text("body")
                await browser.close()
                return content[:3000]  # Return first 3000 chars for LLM context
        except Exception as e:
            logger.error(f"Playwright navigation failed: {e}")
            return f"Error retrieving page: {e}"
