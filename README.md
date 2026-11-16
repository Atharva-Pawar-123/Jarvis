# J.A.R.V.I.S. (Just A Rather Very Intelligent System) 🤖✨
### 100% Offline, Private, Zero-Cost AI Assistant for Personal Hardware

---

## 📌 Project Overview

**JARVIS** is an autonomous, fully local, multimodal AI desktop assistant modeled after the Iron Man persona (Paul Bettany). Engineered specifically for local personal hardware (NVIDIA RTX 3050 6GB VRAM, 16GB RAM), JARVIS operates **completely offline with zero cloud API subscriptions, zero recurring costs, and complete privacy**.

JARVIS coordinates speech recognition, conversational intelligence, reasoning, vision, system automation, and high-speed local image generation through a hybrid desktop interface.

---

## 🏛️ Core Architecture

```
+─────────────────────────────────────────────────────────────────────────────+
|                         USER INTERFACE & ENTRYPOINTS                        |
|  - Voice I/O: OpenWakeWord ("hey_jarvis") + faster-whisper + Piper TTS      |
|  - Desktop App: Electron + React 19 + TailwindCSS + Zustand + Framer Motion |
|  - Browser HUD: HTML5 / WebSocket real-time audio orb & system monitor      |
+─────────────────────────────────────────────────────────────────────────────+
                                       │
                                       ▼
+─────────────────────────────────────────────────────────────────────────────+
|                         CENTRAL NERVOUS SYSTEM                              |
|  - main.py: CLI Orchestrator, Hotword Loop, Audio & Execution Dispatch      |
|  - server/api_server.py: FastAPI v3.0 REST & WebSocket Server (Port 8080)   |
+─────────────────────────────────────────────────────────────────────────────+
       │                                              │
       ▼                                              ▼
+──────────────────────────+       +──────────────────────────────────────────+
|  INTELLIGENT LLM ENGINE  |       |        HYBRID RAG LONG-TERM MEMORY       |
|  - Primary: qwen2.5:7b   |       |  - Semantic Search: ChromaDB (vector)    |
|  - Fast Intent: 1.5b     |       |  - Keyword Search: BM25Okapi             |
|  - Coder: 7b             |       |  - Fusion: Reciprocal Rank Fusion (k=60) |
|  - Vision: llava:7b      |       |  - Auto-fact extraction in background    |
+──────────────────────────+       +──────────────────────────────────────────+
       │
       ▼
+─────────────────────────────────────────────────────────────────────────────+
|                               TOOL REGISTRY                                 |
|  - System Automation: Windows APIs, taskkill, volume, clipboard, hotkeys    |
|  - Unrestricted Image Gen: Local SD WebUI Forge + DreamShaper 8 (GPU)       |
|  - Computer Vision: Screen description, PyTesseract OCR, Webcam Mood        |
|  - Code Sandbox: Sandboxed subprocess Python code execution & fix loop      |
|  - Multi-Agent Orchestration: ReAct Agent + UltraPlan background tasks      |
|  - IoT & Communications: Email (IMAP/SMTP), WhatsApp, Home Assistant       |
+─────────────────────────────────────────────────────────────────────────────+
```

---

## 🚀 Key Features

### 1. Conversational Reasoning & Multi-Agent Planning
- **Dual-Model Intent Classifier**: Sub-200ms intent classification using `qwen2.5:1.5b` with multi-turn conversation awareness.
- **ReAct Agent**: Dynamic Thought-Action-Observation loop that inspects parameters, invokes local tools, and reports verified results.
- **UltraPlan Coordinator**: Background asynchronous task executor that handles complex multi-step goals without blocking voice/chat interactions.
- **Chain-of-Thought (CoT)**: Step-by-step reasoning enclosed in hidden tags before producing spoken responses.

### 2. High-Speed, Uncensored Local Image Generation (Zero-Cost)
- **Embedded Engine**: Powered by an isolated local **SD WebUI Forge** backend (`D:\JARVIS\tools\forge\`).
- **Base Model**: **DreamShaper 8** (`.safetensors`, 2.13 GB), fully capable of both **SFW and unrestricted NSFW** art, anime, and photorealism.
- **GPU Accelerated**: Produces images in **~4–6 seconds** on an RTX 3050 (6GB VRAM) using layer-wise memory offloading and xFormers cross-attention.
- **Prompt Engineering**: JARVIS automatically expands user prompts into artistic concepts with negative prompt filters to prevent anatomical defects.
- **Batch Processing**: Supports rendering multiple variations with automatic completion callbacks and gallery pop-ups.

### 3. Voice & Speech Pipeline
- **Wake Word Detection**: Background `openwakeword` listening continuously for *"hey_jarvis"* with offline-safe loading.
- **Speech-to-Text (STT)**: `faster-whisper` (`small` model) with real-time RMS-based silence cutoff.
- **Streaming Text-to-Speech (TTS)**: Piper TTS (`en_GB-alan-medium.onnx`, Paul Bettany British persona) streaming tokens into sentence buffers with parallel worker pools and zero LLM loop blocking.

### 4. Hybrid Long-Term Memory (RAG)
- Combines dense vector embeddings via **ChromaDB** with sparse lexical matching via **BM25Okapi**.
- Merges results using **Reciprocal Rank Fusion (RRF)**.
- Automatically stores personal facts, user preferences, and prior conversation context across sessions.

### 5. Computer Vision & Screen Intelligence
- Screen capture via `mss` and webcam capture via OpenCV with safe resource disposal.
- Multi-modal visual question answering (VQA) using `llava:7b` / Moondream.
- High-accuracy screen OCR via PyTesseract.
- Facial mood detection via DeepFace.

### 6. Full Desktop Control & Tool Suite
- **App Management**: Open and cleanly terminate applications (`taskkill` sanitized subprocess).
- **Audio Control**: Increase, decrease, or toggle Windows system volume natively via `ctypes`.
- **System Telemetry**: Real-time CPU, RAM, GPU VRAM, disk, and battery reporting.
- **Live Utilities**: Weather fetching (via `wttr.in`), web search, and news updates.
- **Secure Code Engine**: Isolates and executes Python scripts in unique temporary workspaces using the project virtual environment.

---

## 🛠️ Requirements & Prerequisites

### Hardware
- **GPU**: NVIDIA RTX 3050 (Laptop or Desktop) with at least 6GB VRAM (or higher).
- **RAM**: 16 GB System Memory.
- **Disk**: ~15–20 GB free space on `D:\` drive.
- **OS**: Windows 10/11 (64-bit).

### Software
- **Python**: 3.11.x (installed in `D:\JARVIS\venv\`).
- **Node.js**: v18+ & npm (for the React/Electron app).
- **Ollama**: Installed and running locally (`http://localhost:11434`).
- **Models Pulled in Ollama**:
  ```powershell
  ollama pull qwen2.5:7b
  ollama pull qwen2.5:1.5b
  ollama pull qwen2.5-coder:7b
  ollama pull nomic-embed-text
  ollama pull llava:7b
  ```

---

## ⚡ Step-by-Step Instructions to Run JARVIS

### 1. Start Ollama
Ensure the local Ollama service is active:
```powershell
ollama serve
```

---

### 2. Run JARVIS Core (Voice & CLI Mode)
Activate the Python virtual environment and run the main entry point:
```powershell
cd D:\JARVIS
.\venv\Scripts\Activate.ps1
python main.py
```
*What happens:*
- JARVIS loads models, initializes the tool registry, starts the wake-word listener, and greets you with: *"JARVIS online and ready, sir."*
- You can say *"Hey Jarvis"* followed by a command, or type directly into the prompt.

---

### 3. Run the Electron Desktop App (React UI)
To launch the modern desktop UI:
```powershell
cd D:\JARVIS\app
npm run start
```
*What happens:*
- Starts the Vite development server and launches the native Electron desktop client connected to JARVIS's backend on `ws://localhost:8080`.

---

### 4. Run the Standalone API Backend Server
If running headless or integrating external clients:
```powershell
cd D:\JARVIS
.\venv\Scripts\Activate.ps1
python server\api_server.py
```
- REST endpoints and WebSocket stream are hosted at `http://127.0.0.1:8080`.
- Browser HUD overlay available at `http://127.0.0.1:8080/hud`.

---

### 5. Running Local Image Generation (SD Forge)
The local image engine automatically starts in the background when requested. You can also run it manually:
```powershell
cd D:\JARVIS\tools\forge
.\start_forge_api.bat
```
- Hosts the REST API on `http://127.0.0.1:7860`.
- All generated images are stored in `D:\JARVIS\generated_images\`.

---

## 📁 Repository Structure

```
D:\JARVIS\
├── app\                    # Electron + React 19 Frontend
│   ├── electron\main.js    # Electron native wrapper
│   ├── src\                # UI components, state stores, views
│   └── package.json        # Frontend scripts and dependencies
├── config.py               # Global system configuration & hardware paths
├── data\                   # Persistent storage (ChromaDB, SQLite, BM25)
├── generated_images\       # Destination for all generated artwork
├── hud\                    # Web-based HUD static assets
├── main.py                 # Core CLI & Voice orchestration loop
├── modules\                # Modular engines & tools
│   ├── automation.py       # OS, app & clipboard control
│   ├── code_engine.py      # Python sandbox executor
│   ├── image_gen.py        # Local Forge SD + Pollinations fallback
│   ├── intent.py           # Dual-model sub-200ms classifier
│   ├── llm.py              # Intelligent LLM Engine (Ollama wrapper)
│   ├── long_term_memory.py # ChromaDB + BM25 Hybrid RAG
│   ├── react_agent.py      # Autonomous tool ReAct engine
│   ├── stt.py              # Faster-Whisper audio transcription
│   ├── tts.py              # Streaming Piper voice synthesizer
│   ├── vision.py           # Screen capture, OCR & webcam analysis
│   └── wake_word.py        # OpenWakeWord background detector
├── server\                 # FastAPI backend server & WebSocket manager
├── tools\
│   └── forge\              # Isolated SD WebUI Forge portable package
└── venv\                   # Project Python 3.11 virtual environment
```
