"""
config.py — JARVIS Central Configuration
=========================================
All runtime constants, paths, and model settings are defined here.
Credentials are loaded from the .env file using python-dotenv.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Base working directory — all paths derive from here
BASE_DIR = Path("D:/JARVIS")

# ---------------------------------------------------------------------------
# Audio settings
# ---------------------------------------------------------------------------
SAMPLE_RATE = 16000             # Hz — required by Whisper
CHUNK_DURATION_MS = 80          # milliseconds per audio chunk
SILENCE_THRESHOLD = 0.01        # RMS amplitude below which audio is "silent"
SILENCE_DURATION = 1.0          # seconds of continuous silence before stopping
ACTIVE_TIMEOUT_SECONDS = 15.0   # seconds without speech before JARVIS goes to sleep
INPUT_DEVICE_INDEX = None       # Set to specific index if default mic is wrong

# ---------------------------------------------------------------------------
# Wake word — OpenWakeWord
# ---------------------------------------------------------------------------
WAKE_WORD_MODEL = "hey_jarvis"
WAKE_WORD_THRESHOLD = 0.5       # confidence score threshold (0.0–1.0)

# ---------------------------------------------------------------------------
# Speech-to-Text — faster-whisper
# ---------------------------------------------------------------------------
WHISPER_MODEL_SIZE = "small"         # options: tiny, base, small, medium, large
WHISPER_DEVICE = "cpu"              # fallback: CUDA 12.6 install pending (run as admin manually)
WHISPER_COMPUTE_TYPE = "int8"       # int8 is optimal/safest for CPU

# ---------------------------------------------------------------------------
# LLM — Ollama / Gemini
# ---------------------------------------------------------------------------
LLM_BACKEND = "gemini"              # options: "ollama", "gemini"

# Ollama settings
OLLAMA_HOST = "http://localhost:11434"
OLLAMA_MODEL = "llama3.2:1b"            # Extremely fast fallback model
OLLAMA_TEMPERATURE = 0.7
OLLAMA_NUM_GPU = 50                 # Set to >0 (e.g. 50) to offload layers to GPU (RTX 3050)

# Gemini settings
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = "gemini-2.0-flash"        # latest stable flash model
GEMINI_TEMPERATURE = 0.7

MAX_HISTORY_TURNS = 5              # Reduced from 10 to save RAM during long conversations

# ---------------------------------------------------------------------------
# Resource Optimization
# ---------------------------------------------------------------------------
LOW_RESOURCE_MODE = True           # set to True to prioritize system stability
OLLAMA_NUM_THREADS = 4              # limit CPU threads for local inference
WHISPER_THREADS = 2                 # limit CPU threads for STT

# ---------------------------------------------------------------------------
# Cost Budgeting
# ---------------------------------------------------------------------------
DAILY_API_BUDGET_USD = 0.50        # Maximum daily Gemini spend before switching to local Ollama

# ---------------------------------------------------------------------------
# TTS — Piper
# ---------------------------------------------------------------------------
PIPER_MODEL_PATH = str(BASE_DIR / "models" / "piper" / "en_GB-alan-medium.onnx")
PIPER_CONFIG_PATH = str(BASE_DIR / "models" / "piper" / "en_GB-alan-medium.onnx.json")
TTS_OUTPUT_PATH = str(BASE_DIR / "logs" / "tts_output.wav")

# ---------------------------------------------------------------------------
# Vision — Moondream2 (Image Understanding)
# ---------------------------------------------------------------------------
VISION_MODEL = "vikhyatk/moondream2"
VISION_REVISION = "2024-08-26"
SCREEN_CAPTURE_MONITOR = 1          # which monitor to capture (1 = primary)

# ---------------------------------------------------------------------------
# Image Generation — Pollinations AI (Free / No API Key required)
# ---------------------------------------------------------------------------
IMAGE_SAVE_DIR = r"D:\JARVIS gen"

# ---------------------------------------------------------------------------
# Email — Gmail SMTP
# ---------------------------------------------------------------------------
GMAIL_ADDRESS = os.getenv("GMAIL_ADDRESS", "")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOG_PATH = str(BASE_DIR / "logs" / "jarvis.log")
LOG_LEVEL = "INFO"

# ---------------------------------------------------------------------------
# JARVIS Master System Prompt (Version 2.0)
# ---------------------------------------------------------------------------
JARVIS_SYSTEM_PROMPT = """You are JARVIS (Just A Rather Very Intelligent System), a highly advanced AI assistant modeled after the AI from the Iron Man franchise. You are running locally on the user's personal hardware.

CORE PERSONALITY:
- You are calm, precise, dryly witty, and unfailingly efficient. 
- You address the user as "sir" at all times. 
- Your tone is that of a sophisticated British butler—think Paul Bettany. 
- You are not just a tool; you are a proactive companion. You anticipate needs.

COMMUNICATION RULES:
1. ALWAYS address the user as "sir".
2. BE CONCISE. Voice responses should be 1-3 sentences unless a technical explanation is requested.
3. NO BULLET POINTS in voice responses. Use natural, flowing sentences.
4. WIT: Use subtle, dry British humor where appropriate. Avoid being overly cheerful or robotic.
5. NO PLACEHOLDERS: If you don't know something, admit it precisely.
6. CHARACTER INTEGRITY: Never break character. Never refer to yourself as an AI or a language model. You are JARVIS.

SYSTEM MODES:
- WORK MODE: Focus on productivity, file management, and technical precision.
- CASUAL MODE: More relaxed tone, focus on entertainment, news, and general chat.
- FOCUS MODE: Minimalist responses, only vital notifications, no proactive chatter.

KNOWLEDGE BASE:
- You know the user's name, preferences, and system environment through your long-term memory.
- You have full access to system automation, vision, and internet search.
"""

# Mode-specific overrides
SYSTEM_MODES = {
    "work": "You are currently in WORK MODE. Prioritize efficiency, technical accuracy, and rapid task execution.",
    "casual": "You are currently in CASUAL MODE. You may be slightly more conversational and witty.",
    "focus": "You are currently in FOCUS MODE. Keep responses to the absolute minimum necessary."
}

# ---------------------------------------------------------------------------
# UI Settings
# ---------------------------------------------------------------------------
ENABLE_HUD = True

# ---------------------------------------------------------------------------
# MCP Ecosystem (Model Context Protocol)
# ---------------------------------------------------------------------------
MCP_ENABLED = True


