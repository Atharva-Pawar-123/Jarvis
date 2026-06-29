"""
modules/hud.py — JARVIS Iron Man Style HUD Overlay
==================================================
A transparent, borderless, always-on-top tkinter overlay
that displays JARVIS's current state and transcription.
"""

import logging
import threading
import tkinter as tk

logger = logging.getLogger(__name__)


class JarvisHUD:
    """
    Transparent GUI overlay for JARVIS status and text.
    Runs its own tkinter main loop in a background thread.
    """

    def __init__(self) -> None:
        self.root = None
        self.status_var = None
        self.user_var = None
        self.jarvis_var = None
        
        self.visible = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def _run_loop(self) -> None:
        """
        Initialize and run the tkinter main loop.
        Must be run in its own thread.
        """
        self.root = tk.Tk()
        self.root.overrideredirect(True)  # No window decorations
        self.root.attributes("-topmost", True)  # Always on top
        self.root.attributes("-alpha", 0.85)  # Slight transparency
        
        # Make the black background entirely transparent
        self.root.configure(bg="black")
        self.root.wm_attributes("-transparentcolor", "black")

        # Position at bottom right (assuming ~1920x1080 screen, adjust dynamically)
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        window_width = 450
        window_height = 150
        x = screen_width - window_width - 50
        y = screen_height - window_height - 100
        self.root.geometry(f"{window_width}x{window_height}+{x}+{y}")

        # StringVars for dynamic updating
        self.status_var = tk.StringVar(value="[ ONLINE ]")
        self.user_var = tk.StringVar(value="You: ...")
        self.jarvis_var = tk.StringVar(value="JARVIS: Ready.")

        # Status Label (Cyan)
        self.status_label = tk.Label(
            self.root,
            textvariable=self.status_var,
            font=("Consolas", 12, "bold"),
            fg="#00FFFF",  # Cyan
            bg="black",
            anchor="e",
            justify="right"
        )
        self.status_label.pack(fill="x", pady=(0, 10))

        # User Text (White)
        self.user_label = tk.Label(
            self.root,
            textvariable=self.user_var,
            font=("Consolas", 10),
            fg="white",
            bg="black",
            anchor="e",
            justify="right",
            wraplength=400
        )
        self.user_label.pack(fill="x", pady=2)

        # JARVIS Text (Cyan/Blue)
        self.jarvis_label = tk.Label(
            self.root,
            textvariable=self.jarvis_var,
            font=("Consolas", 10, "italic"),
            fg="#4da6ff",
            bg="black",
            anchor="e",
            justify="right",
            wraplength=400
        )
        self.jarvis_label.pack(fill="x", pady=2)

        logger.info("HUD Overlay initialized.")
        self.root.mainloop()

    def set_status(self, status: str, color: str = "#00FFFF") -> None:
        """
        Update the top status indicator (e.g. [ LISTENING ]).
        """
        if self.root and self.status_var:
            self.root.after(0, lambda: self.status_var.set(f"[ {status} ]"))
            self.root.after(0, lambda: self.status_label.configure(fg=color))

    def set_user_text(self, text: str) -> None:
        """
        Update the transcription of what the user just said.
        """
        if self.root and self.user_var:
            self.root.after(0, lambda: self.user_var.set(f"You: {text}"))

    def set_jarvis_text(self, text: str) -> None:
        """
        Update the transcription of what JARVIS is saying.
        """
        if self.root and self.jarvis_var:
            self.root.after(0, lambda: self.jarvis_var.set(f"JARVIS: {text}"))

    def toggle(self) -> None:
        """
        Toggle the visibility of the HUD.
        """
        if self.root:
            if self.visible:
                self.root.after(0, self.root.withdraw)
            else:
                self.root.after(0, self.root.deiconify)
            self.visible = not self.visible
