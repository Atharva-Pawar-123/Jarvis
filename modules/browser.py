"""
modules/browser.py — JARVIS Browser Automation
==============================================
Controls Google Chrome using Selenium for web navigation and searching.
Uses webdriver-manager for seamless driver installation.
"""

import logging
from typing import Optional

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from webdriver_manager.chrome import ChromeDriverManager

logger = logging.getLogger(__name__)


class BrowserController:
    """
    Automates web browser interactions.
    """

    def __init__(self) -> None:
        self.driver: Optional[webdriver.Chrome] = None

    def _ensure_driver(self) -> None:
        """Initialize the Chrome driver if it's not already running."""
        if self.driver is None:
            logger.info("Starting Chrome driver...")
            chrome_options = Options()
            # To keep the browser open after script finishes, use detach
            chrome_options.add_experimental_option("detach", True)
            # Add some stability flags
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            logger.info("Browser driver initialized successfully.")

    def open_url(self, url: str) -> str:
        """Navigate to a specific URL."""
        if not url:
            return "I need a URL to open, sir."
            
        self._ensure_driver()
        if not url.startswith("http"):
            url = "https://" + url
            
        try:
            logger.info(f"Navigating to {url}")
            self.driver.get(url)
            return f"Opening {url}, sir."
        except Exception as exc:
            logger.error(f"Failed to open URL {url}: {exc}")
            return f"I couldn't reach that website, sir. Error: {str(exc)}"

    def search(self, query: str) -> str:
        """Search Google for a query."""
        if not query:
            return "What should I search for, sir?"
            
        self._ensure_driver()
        try:
            logger.info(f"Searching for: {query}")
            self.driver.get("https://www.google.com")
            
            # Find the search box (Google's input name is 'q')
            search_box = self.driver.find_element(By.NAME, "q")
            search_box.send_keys(query)
            search_box.send_keys(Keys.RETURN)
            
            return f"Searching for '{query}', sir."
        except Exception as exc:
            logger.error(f"Browser search failed: {exc}")
            return "I encountered an error while trying to search, sir."

    def close(self) -> str:
        """Close the browser instance."""
        if self.driver:
            self.driver.quit()
            self.driver = None
            return "Browser closed."
        return "The browser is already closed."

    def open_incognito(self, url: str = "") -> str:
        """Open a new incognito/private browser window (no Selenium needed).

        Falls through Chrome → Edge → fallback webbrowser.
        """
        import os
        import subprocess

        chrome_paths = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        ]
        edge_paths = [
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        ]

        for path in chrome_paths:
            if os.path.exists(path):
                args = [path, "--incognito"]
                if url:
                    args.append(url)
                try:
                    subprocess.Popen(args)
                    where = f" at {url}" if url else ""
                    return f"Opened incognito Chrome window{where}, sir."
                except Exception as exc:
                    logger.error(f"Failed to open Chrome incognito: {exc}")

        for path in edge_paths:
            if os.path.exists(path):
                args = [path, "--inprivate"]
                if url:
                    args.append(url)
                try:
                    subprocess.Popen(args)
                    where = f" at {url}" if url else ""
                    return f"Opened InPrivate Edge window{where}, sir."
                except Exception as exc:
                    logger.error(f"Failed to open Edge InPrivate: {exc}")

        # Absolute fallback — open with webbrowser (won't be incognito)
        import webbrowser
        target = url if url else "about:blank"
        webbrowser.open(target)
        logger.warning("Could not find Chrome or Edge for incognito mode. Opened standard browser.")
        return "Sir, I couldn't find Chrome or Edge for incognito mode. I opened a standard browser window instead."
