# J.A.R.V.I.S. (Just A Rather Very Intelligent System) 🤖✨
### Fully Local, Autonomous, 100% Offline AI Assistant for Personal Hardware (V2.4)

---

## 📌 Project Overview

**JARVIS** is an autonomous, fully local, multimodal AI desktop assistant modeled after the iconic Iron Man persona (voiced in the calm, witty, and precise British cadence of Paul Bettany). Engineered specifically for local personal hardware (optimized for NVIDIA RTX 3050 6GB VRAM, 16GB RAM, Windows 10/11), JARVIS operates **completely offline with zero cloud API subscriptions, zero recurring costs, and total data privacy**.

With the completion of **V2.4 Image Studio Pro & Multi-Session Visual Suite**, JARVIS delivers an enterprise-grade, self-correcting desktop intelligence platform:
- **Image Studio Pro (Grok Imagine Architecture)**: Unified 3-in-1 creative studio featuring text-to-image generation, a dedicated **Edit Canvas** for instruction-guided img2img & inpainting, and an asset **Library** gallery.
- **Direct Computer Storage Upload**: Upload any `.png`, `.jpg`, or `.webp` file from local storage via drag-and-drop or file picker with automatic EXIF stripping and sRGB sanitization.
- **Grok-Style Visual Session Rail**: Independent visual sessions with 3-image miniature preview cards, allowing users to switch between editing canvases without losing work.
- **Complete Zero-Trace Deletion System**: Full user control to delete any individual conversation, Imagine visual session, or image asset. Permanent file unlinking (`Path.unlink()`) ensures zero residue remains on disk.
- **Edit Canvas Model Selector & Visual Alerts**: Dynamic checkpoint selector in Edit Canvas and automated SD-Forge background launcher with informative error banners.
- **Persistent Asset Database (`image_studio.db`)**: Full SQLite catalog maintaining version lineage (e.g., Upload &rarr; Edit 1 &rarr; Edit 2), favorite flags, prompt metadata, and dimensions.
- **Session & Memory Persistence on Reboot**: Resolved previous session wipe bug by synchronizing `activeSessionId` across `localStorage` and SQLite, ensuring conversations and visual assets survive restarts.
- **Next-Gen Command Center HUD**: Futuristic military/sci-fi command dashboard with live clock, central holographic 3D particle orb, agent status matrix, mission timeline, live intelligence feed, hardware gauges, constellation memory insights, and one-click voice dock.
- **Hardware-Aware GPU Scheduler**: Manages mutually exclusive execution between Qwen LLM reasoning, LLaVA vision, and Stable Diffusion Forge image generation to eliminate CUDA Out-of-Memory crashes on 6GB VRAM GPUs.
- **100% Offline Diffusion Studio**: Fully local generation powered strictly by SD WebUI Forge with hot-swapping checkpoints (DreamShaper 8, Realistic Vision V5.1, FLUX.1 Schnell) and adaptive parameters. Zero cloud dependencies.

---

## 🏛️ Core Architecture & Models

```
+─────────────────────────────────────────────────────────────────────────────+
|                         USER INTERFACE & ENTRYPOINTS                        |
|  - Desktop App: Electron + React 19 + TailwindCSS + Zustand + Lucide        |
|    * 🌌 Command Center HUD (Default sci-fi landing, 3D orb, mission feeds)  |
|    * 🎨 Image Studio Pro (Generate | Edit Canvas + Inpaint | Visual Library)|
|    * 💬 Chat View (ChatGPT/Claude-style streaming & autonomous reasoning)   |
|    * 🎙️ Voice View (Push-to-talk Arc Reactor Orb, transcript, British TTS)   |
|    * 📊 HUD Dashboard (Real-time CPU, RAM, GPU VRAM & system telemetry)     |
|    * 📋 Task Center (Autonomous DAG launcher, progress bars, cancellation)  |
|    * 🧠 4-Tier Memory Inspector (Working, Episodic, Semantic RAG, Procedural|
|    * ⚙️ Settings Configuration (Model selector, TTS switches, API keys)    |
|  - Voice Daemon: OpenWakeWord ("hey_jarvis") + faster-whisper + Piper TTS   |
+─────────────────────────────────────────────────────────────────────────────+
                                       │
                                       ▼
+─────────────────────────────────────────────────────────────────────────────+
|                    UNIFIED RUNTIME CONTAINER (JarvisRuntime)                |
|  - Unified Agent Orchestrator: Multi-step reasoning loops & tool calling    |
|  - server/api_server.py: FastAPI REST & Scoped WebSocket Server (Port 8080) |
|  - Image Studio DB & Engine: SQLite catalog, img2img inpaint, upload handler|
|  - Persistent Task Engine: SQLite checkpointing with cancellation tokens    |
+─────────────────────────────────────────────────────────────────────────────+
                                       │
        ┌──────────────────────────────┼──────────────────────────────┐
        ▼                              ▼                              ▼
+─────────────────+          +───────────────────+          +──────────────────+
| COGNITIVE CORE  |          |   SENSORY ENGINE  |          | SECURITY & TOOLS |
| (Local Ollama)  |          |   (Audio & Vision)|          | (Sandbox & Skills)
| - qwen2.5:7b    |          | - faster-whisper  |          | - Permission Gate|
| - qwen2.5:1.5b  |          | - Piper TTS (alan)|          | - Hardened Sandbox
| - nomic-embed   |          | - OpenWakeWord    |          | - Win32 UI & Web |
| - llava:7b      |          | - SD WebUI Forge  |          | - Dynamic Skills |
+─────────────────+          +───────────────────+          +──────────────────+
```

### Models & Subsystems
- **Primary Reasoning (`qwen2.5:7b`)**: General conversational intelligence, multi-step goal decomposition, and ReAct agent tool calling.
- **Intent Classifier (`qwen2.5:1.5b`)**: Fast, deterministic intent extraction and slot-filling with history context.
- **Vision Engine (`llava:7b`)**: Screen understanding, OCR via PyTesseract, and multimodal conversational image inspection.
- **Hybrid Memory (`nomic-embed-text` + ChromaDB + BM25)**: Vector embeddings + lexical keywords fused via Reciprocal Rank Fusion (RRF).
- **Speech-to-Text (`faster-whisper` small on CUDA)**: Transcribes voice in ~0.04s with Silero VAD adaptive silence detection (~0.6s).
- **Text-to-Speech (Piper `en_GB-alan-medium.onnx`)**: Crisp British accent with ~50 ms chunked playback and instant interruption.
- **Image Generation & Editing (Local SD WebUI Forge on GPU)**: Multi-model suite featuring local Stable Diffusion Forge (DreamShaper 8, Realistic Vision V5.1, FLUX.1 Schnell) running directly on the NVIDIA RTX GPU for both text-to-image and inpainting/img2img. 100% offline with zero cloud dependencies.

---

## 🚀 How to Run JARVIS (Step-by-Step)

Follow these exact steps to launch the complete system.

### Prerequisites Check
1. Ensure **Ollama** is running in your background/system tray with required models pulled:
   ```powershell
   ollama pull qwen2.5:7b
   ollama pull qwen2.5:1.5b
   ollama pull nomic-embed-text
   ollama pull llava:7b
   ```
2. Ensure you have the Python virtual environment created in `d:\JARVIS\venv`.

---

### Step 1: Launch Desktop App (Recommended - Single Command)

The easiest way to run JARVIS is via Electron, which automatically starts the backend server, launches Vite, and opens the native desktop app:

```powershell
cd D:\JARVIS\app
npm run electron:dev
```

*Electron will launch `server/api_server.py`, wait until the backend reports healthy on port 8080, bundle Vite, and present the Command Center HUD window.*

---

### Step 2: Running in Web Browser Mode (Alternative)

If you prefer using your standard web browser instead of the Electron container:

**Terminal 1 — Backend API Server:**
```powershell
cd D:\JARVIS
.\venv\Scripts\Activate.ps1
python -m uvicorn server.api_server:app --host 127.0.0.1 --port 8080
```

**Terminal 2 — Frontend UI:**
```powershell
cd D:\JARVIS\app
npm run dev
```
Navigate to **`http://localhost:5173`** in Chrome, Edge, or Brave.

---

### Step 3: Running Pure Voice Daemon (`main.py`)

To run JARVIS solely as a hands-free, background voice assistant responding to wake words:

```powershell
cd D:\JARVIS
.\venv\Scripts\Activate.ps1
python main.py
```
*JARVIS will initialize audio hardware, calibrate ambient noise, and say: "JARVIS online and ready, sir." You can now say "Hey Jarvis" to speak.*

---

### Step 4: Running Local Image Generation Engine (SD Forge)

To use Image Studio Pro for generating or editing images on your GPU:

```powershell
cd D:\JARVIS\tools\forge
.\start_forge_api.bat
```
*Launches SD WebUI Forge on port 7860 with `--always-offload-from-vram` and xFormers optimizations.*

---

### Step 5: Running the Automated Test Suite

To verify system integrity, run the complete 48-test regression suite:

```powershell
cd D:\JARVIS
.\venv\Scripts\Activate.ps1
pytest -q tests/v2/
```

---

## 🌟 Features & Capabilities Overview

| Module | What It Does | How to Access / Activate |
|---|---|---|
| **🌌 Command Center HUD** | Futuristic mission dashboard with 3D orb, real-time telemetry, agent matrix, and timeline | Default landing tab on app launch |
| **🎨 Image Studio Pro** | 3-in-1 visual suite: Text-to-Image, Edit Canvas (img2img/inpaint), and Masonry Library | Click **Image Studio** in sidebar |
| **📤 Storage Image Upload** | Upload images from your computer for editing or chatting | Click **Upload Image** or drag-and-drop onto canvas |
| **🖼️ Grok Imagine Sessions** | Multi-session rail with 3-image preview cards & independent states | Left rail in Image Studio |
| **🗑️ Zero-Trace Deletion** | Context menu deletion for conversations, sessions, and individual images with physical file unlinking | Click 3-dots `...` menu on chats, session cards, or image previews |
| **💬 Conversations & Chat** | Full-context conversational reasoning with ChatGPT/Claude-style streaming | Click **Conversations** tab in sidebar |
| **🎙️ Voice Interface** | Wake-word ("Hey Jarvis") + Arc Reactor push-to-talk orb + British TTS | Speak aloud or click microphone button |
| **🧠 4-Tier Memory** | Persistent Working, Episodic, Semantic RAG, and Procedural habits | Click **Memory** in sidebar |
| **👁️ Vision & Inspection** | Multimodal image understanding and OCR via LLaVA & PyTesseract | Click **Chat with Image** in studio or ask in chat |
| **🔒 Security Authorization** | Cryptographic approval prompts for high-risk system commands | Triggers automatically on sensitive tools |
| **⚡ Task DAG Engine** | Background multi-step autonomous workflows surviving reboots | Click **Tasks** tab in sidebar |
