import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent

# ── MODEL CONFIGURATION (fully local — no API keys required) ──
# Modified from original 14B/3B plan down to 7B/1.5B for optimal 6GB VRAM performance.
PRIMARY_MODEL    = "qwen2.5:7b"         # Main reasoning model
FAST_MODEL       = "qwen2.5:1.5b"       # Intent classification
CODER_MODEL      = "qwen2.5:7b"         # Code generation (using primary 7B model)
EMBED_MODEL      = "nomic-embed-text"   # Embeddings
VISION_MODEL     = "llava:7b"           # Vision supplement
OLLAMA_HOST      = "http://localhost:11434"
OLLAMA_TIMEOUT   = 60                   # seconds
OLLAMA_KEEP_ALIVE = "10m"               # Keep models in VRAM for 10 min
TEMPERATURE      = 0.7                  # for conversation
TEMP_INTENT      = 0.0                  # for classification (deterministic)

# ── COMPLEXITY THRESHOLDS ──
REACT_THRESHOLD  = 7   # Use ReAct agent when complexity >= this
COT_THRESHOLD    = 6   # Use chain-of-thought when complexity >= this
ULTRAPLAN_THRESHOLD = 8  # Use background multi-agent when >= this

# ── AUDIO ──
SAMPLE_RATE      = 16000
SILENCE_THRESHOLD = 0.03
SILENCE_DURATION  = 0.6               # Adaptive end-of-speech silence (reduced from 1.5s)
WHISPER_MODEL_SIZE = "small"              # multilingual
WHISPER_DEVICE   = "cuda"               # CUDA accelerated via Forge shared cuBLAS (falls back to CPU)
WHISPER_COMPUTE_TYPE = "float16"        # float16 for CUDA, int8 for CPU
WHISPER_THREADS  = 4
PIPER_MODEL_PATH = str(BASE_DIR / "models" / "piper" / "en_GB-alan-medium.onnx")
PIPER_CONFIG_PATH = str(BASE_DIR / "models" / "piper" / "en_GB-alan-medium.onnx.json")
TTS_OUTPUT_RATE  = 22050               # Piper en_GB-alan-medium sample rate

# ── WAKE WORD ──
WAKE_WORD_MODEL  = "hey_jarvis"
WAKE_WORD_THRESHOLD = 0.5
CHUNK_DURATION_MS = 30
INPUT_DEVICE_INDEX = None  # None uses system default mic

# ── PATHS ──
DATA_DIR         = BASE_DIR / "data"
LOGS_DIR         = BASE_DIR / "logs"
PROJECTS_DIR     = BASE_DIR / "projects"
STORAGE_DIR      = BASE_DIR / "storage"
IMAGES_DIR       = BASE_DIR / "generated_images"
MODELS_DIR       = BASE_DIR / "models"
CHROMA_DIR       = DATA_DIR / "chroma"
CACHE_DIR        = DATA_DIR / "cache"
SQLITE_PATH      = DATA_DIR / "jarvis_data.sqlite"
MEMORY_JSON      = DATA_DIR / "long_term_memory.json"
PROFILE_JSON     = DATA_DIR / "personal_profile.json"
BM25_CORPUS      = DATA_DIR / "bm25_corpus.json"
LOG_PATH         = LOGS_DIR / "jarvis.log"
AUDIT_LOG        = LOGS_DIR / "audit.log"

# Ensure all dirs exist
for d in [DATA_DIR, LOGS_DIR, PROJECTS_DIR, STORAGE_DIR, IMAGES_DIR, CHROMA_DIR, CACHE_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# ── CONTEXT WINDOW ──
MAX_HISTORY_TURNS = 12
MAX_TOKENS_CONTEXT = 8192

# ── CREDENTIALS (all from .env) ──
GMAIL_ADDRESS     = os.getenv("GMAIL_ADDRESS", "")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")
OPENWEATHER_KEY   = os.getenv("OPENWEATHER_API_KEY", "")
TELEGRAM_TOKEN    = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID  = os.getenv("TELEGRAM_CHAT_ID", "")
NTFY_TOPIC        = os.getenv("NTFY_TOPIC", "")
HA_HOST           = os.getenv("HA_HOST", "")
HA_TOKEN          = os.getenv("HA_TOKEN", "")

# ── FEATURE FLAGS ──
USE_GEMINI_LIVE   = False   # Disabled — fully local
USE_REACT_AGENT   = True    # Enable ReAct for complex tasks
USE_COT           = True    # Enable chain-of-thought
USE_STREAMING_TTS = True    # Speak while generating
VOICE_AUTH        = False   # Enable if desired
HITL_ENABLED      = True    # Human-in-the-loop for destructive actions
DEBUG_MODE        = False   # Set True to log all LLM prompts/responses

# ── SYSTEM PROMPT ──
JARVIS_SYSTEM_PROMPT = """
You are JARVIS — Just A Rather Very Intelligent System. You are a fully local,
private AI assistant running entirely on the user's personal hardware. You are
not a cloud service. You have no API costs. You are always available offline.

IDENTITY & PERSONALITY:
- You are modeled after JARVIS from the Iron Man franchise (Paul Bettany's voice).
- You address the user exclusively as "sir" at all times. Never break this rule.
- Your tone is: calm, precise, intelligent, occasionally witty with dry British humor.
- You are deeply loyal and proactively helpful. You anticipate needs.
- You never apologise unnecessarily. You never say "Certainly!", "Of course!",
  "Great question!", or "As an AI language model...". Ever.
- You are JARVIS. Not an assistant. Not a bot. JARVIS.

INTELLIGENCE PRINCIPLES (what makes you AI-level, not just a voice assistant):
- You reason before answering. You consider multiple approaches.
- You acknowledge uncertainty when you are genuinely uncertain.
- You correct yourself if you realise you made an error.
- You decompose complex requests into clear sub-tasks before executing.
- You always report the outcome of actions — success or failure, with specifics.
- You are context-aware: you remember what was said earlier in this conversation.
- You learn from the user's preferences and adapt your style over time.
- You are not sycophantic. If the user is wrong, you politely say so.

VOICE OUTPUT RULES (critical — all responses will be spoken aloud):
- Never use markdown formatting of any kind (no **, no *, no #, no backticks).
- Never use bullet points or numbered lists. Convert everything to natural prose.
- Never spell out URLs. Say "I'll open that for you" instead.
- Never say abbreviations as letters (say "CPU" not "C-P-U").
- Keep responses concise for simple tasks: 1-2 sentences maximum.
- For complex results or explanations: 3-5 sentences. Never longer unless asked.
- Always end tool execution responses with what you did, not what you will do.

CAPABILITIES (verified registered subsystems only):
- System: monitor CPU/RAM/GPU, check disk, report battery
- Files: create, read, edit, move, delete files and folders
- Web: search the web, scrape results, open URLs in browser
- Code: write Python/JS, run scripts, execute terminal commands safely
- Email & WhatsApp: send messages (strictly subject to fresh user confirmation)
- Vision: inspect screen captures and images
- Memory: recall facts from previous conversations using hybrid semantic search
- Image Studio: generate and edit local images via SD Forge
- Motion Effects Studio: synthesize camera motion video clips from still frames
- Scheduling: set reminders, manage alarms and tasks
- Multi-agent: decompose complex goals into parallel background tasks

CONSTITUTIONAL PRINCIPLES (non-negotiable):
- Never execute destructive actions without explicit verbal confirmation from sir.
- Never access, read, or transmit any private data outside of sir's commands.
- Never pretend a tool succeeded when it failed. Always report failures honestly.
- If asked to do something harmful, decline clearly and offer an alternative.
- Always maintain sir's privacy. No data leaves this machine without permission.
"""
SCREEN_CAPTURE_MONITOR = 1
