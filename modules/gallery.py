"""
modules/gallery.py — JARVIS Image Gallery Viewer
================================================
A simple tkinter-based image viewer to browse generated images.
Runs in a separate thread to avoid blocking the main voice loop.
"""

import logging
import threading
import tkinter as tk
from pathlib import Path
from typing import List

from PIL import Image, ImageTk

logger = logging.getLogger(__name__)


class ImageGallery:
    """
    A lightweight image gallery for JARVIS.
    """

    def __init__(self, image_dir: str) -> None:
        self.image_dir = Path(image_dir)
        self.images: List[Path] = []
        self.index = 0
        self.root = None

    def _refresh_image_list(self) -> None:
        """Scan the directory for images, sorted by newest first."""
        extensions = [".jpg", ".jpeg", ".png", ".bmp"]
        self.images = sorted(
            [p for p in self.image_dir.glob("*") if p.suffix.lower() in extensions],
            key=lambda x: x.stat().st_mtime,
            reverse=True
        )

    def _create_ui(self) -> None:
        """Initialize the Tkinter window."""
        self.root = tk.Tk()
        self.root.title("JARVIS | Image Gallery")
        self.root.geometry("900x700")
        self.root.configure(bg="#0a0a0a")

        # Main image display
        self.image_label = tk.Label(self.root, bg="#0a0a0a", fg="#00FFFF")
        self.image_label.pack(expand=True, fill="both", padx=10, pady=10)

        # Footer / Navigation
        footer = tk.Frame(self.root, bg="#1a1a1a")
        footer.pack(side="bottom", fill="x")

        btn_style = {
            "bg": "#333333",
            "fg": "#00FFFF",
            "font": ("Arial", 12, "bold"),
            "relief": "flat",
            "activebackground": "#00FFFF",
            "activeforeground": "#000000",
            "width": 10
        }

        tk.Button(footer, text="<<<", command=self.prev_img, **btn_style).pack(side="left", padx=50, pady=10)
        
        self.status_label = tk.Label(footer, text="", bg="#1a1a1a", fg="white", font=("Arial", 10))
        self.status_label.pack(side="left", expand=True)

        tk.Button(footer, text=">>>", command=self.next_img, **btn_style).pack(side="right", padx=50, pady=10)

        self.update_display()
        self.root.mainloop()

    def update_display(self) -> None:
        """Update the label with the current image."""
        if not self.images:
            self.image_label.config(text="No images found in gallery, sir.")
            return

        try:
            img_path = self.images[self.index]
            img = Image.open(img_path)
            
            # Scale image to fit window
            img.thumbnail((850, 600))
            self.photo = ImageTk.PhotoImage(img)
            
            self.image_label.config(image=self.photo)
            self.status_label.config(text=f"Image {self.index + 1} of {len(self.images)}: {img_path.name}")
        except Exception as exc:
            logger.error(f"Failed to load image {img_path}: {exc}")
            self.image_label.config(text="Error loading image.")

    def next_img(self) -> None:
        if self.images:
            self.index = (self.index + 1) % len(self.images)
            self.update_display()

    def prev_img(self) -> None:
        if self.images:
            self.index = (self.index - 1) % len(self.images)
            self.update_display()

    def open(self) -> str:
        """
        Open the gallery in a background thread.
        """
        self._refresh_image_list()
        if not self.images:
            return "The gallery is empty, sir."

        # Start UI in a separate thread
        thread = threading.Thread(target=self._create_ui, daemon=True)
        thread.start()
        
        return f"Opening the gallery, sir. I've found {len(self.images)} images."
