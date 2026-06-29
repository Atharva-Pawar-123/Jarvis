"""
modules/gaming.py — JARVIS Gaming Enhancements
==============================================
Monitors system processes to detect if the user is playing a game 
(Steam, Epic Games, Riot, etc.). This allows JARVIS to auto-mute or
enter 'Gaming Mode' to prevent accidental wake-word triggers during Discord calls.
"""

import logging
import psutil
import time
import threading

logger = logging.getLogger(__name__)

class GamingMonitor:
    def __init__(self, callback=None):
        self.callback = callback
        self.is_gaming = False
        self.current_game = None
        self._stop_event = threading.Event()
        
        # Add primary launchers to ignore, we want to detect the *actual games* 
        # or just assume if steam is using heavy CPU, but detecting launchers is easier.
        # Actually, detecting popular launchers running a child game is best, 
        # but for simplicity, we can look for known game executables or launchers.
        self.launchers = ["steam.exe", "epicgameslauncher.exe", "riotclientux.exe", "vanguard.exe", "battle.net.exe"]
        
        # We can also detect full screen applications, but process scanning is safer
        self._thread = None

    def start(self):
        if self._thread is None:
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
            self._thread.start()
            logger.info("Gaming Monitor started.")

    def stop(self):
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2)
            self._thread = None
            logger.info("Gaming Monitor stopped.")

    def _monitor_loop(self):
        while not self._stop_event.is_set():
            game_detected = self._detect_game()
            
            if game_detected != self.is_gaming:
                self.is_gaming = game_detected
                if self.is_gaming:
                    logger.info("Gaming mode activated: Game detected.")
                    if self.callback:
                        self.callback(True)
                else:
                    logger.info("Gaming mode deactivated.")
                    if self.callback:
                        self.callback(False)
            
            # Check every 15 seconds to minimize CPU impact
            time.sleep(15)

    def _detect_game(self):
        # A simple heuristic: if a known launcher is running AND it's consuming significant resources,
        # OR if we detect known heavy games. 
        # For an AI assistant, just checking if the launcher is running is often enough,
        # but people leave Steam open in the background.
        # Better heuristic: check if any process has "game" in its name or is a known game,
        # or use Windows APIs to check if a fullscreen app is running.
        # For simplicity and cross-platform compatibility, let's use a basic process list check.
        
        # For a truly robust system, we would query the Steam API or check window focus.
        # Here we'll do a basic check: if Discord + Launcher are running, we might be gaming,
        # but let's stick to checking if a known game is in the foreground using ctypes.
        try:
            import ctypes
            user32 = ctypes.windll.user32
            
            # Get foreground window handle
            hwnd = user32.GetForegroundWindow()
            if hwnd:
                import ctypes.wintypes
                pid = ctypes.wintypes.DWORD()
                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                
                if pid.value > 0:
                    try:
                        p = psutil.Process(pid.value)
                        name = p.name().lower()
                        # Games often run as full-screen executables.
                        # Some common markers
                        if "game" in name or name in ["csgo.exe", "valorant-win64-shipping.exe", "dota2.exe", "overwatch.exe", "r5apex.exe", "hl2.exe", "eldenring.exe", "cyberpunk2077.exe", "gta5.exe"]:
                            self.current_game = name
                            return True
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
                        
        except Exception as e:
            logger.warning(f"Error detecting foreground game: {e}")
            
        self.current_game = None
        return False
