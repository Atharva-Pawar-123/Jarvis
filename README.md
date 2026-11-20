# J.A.R.V.I.S. (Just A Rather Very Intelligent System) 🤖✨
### Fully Local, Autonomous, 100% Offline AI Assistant for Personal Hardware (V3.0.2)

---

## 📌 Project Overview

**JARVIS** is an autonomous, fully local, multimodal AI desktop assistant modeled after the iconic Iron Man persona (voiced in the calm, witty, and precise British cadence of Paul Bettany). Engineered specifically for local personal hardware (optimized for NVIDIA RTX 3050 6GB VRAM, 16GB RAM, Windows 10/11), JARVIS operates **completely offline with zero cloud API subscriptions, zero recurring costs, and total data privacy**.

With the rollout of **V3.0.2 Reliability & Engineering Quality Release**, JARVIS addresses critical implementation gaps identified during architectural reviews:
- **Imagine Video Studio (V3.0 Motion Engine)**: Calibrated for 6GB consumer GPUs, synthesizing fluid cinematic camera motion clips (zoom in, zoom out, pan, drift) from keyframes into MP4/WEBM with exact filesystem path alignment and an interactive looping preview player.
- **Dedicated Video Asset Library**: Full `<video>` element support in the Library gallery with live hover-to-play scrubbing, video type filtering (`video`), and one-click playback in the Imagine preview modal.
- **True Foreground Segmentation**: Advanced OpenCV GrabCut foreground isolation with ControlNet ADE20K semantic fallback, replacing color-threshold heuristics for robust subject cutouts and background replacement.
- **Durable SQLite Memory Queue (`memory_queue.sqlite`)**: True reboot-safe sequential task queue that recovers and resumes pending fact extraction jobs upon backend restart.
- **Full Workspace State Reconstruction**: Multi-reference image deck, selected models, canvas settings, active tabs, and sliders are automatically persisted to SQLite per-session and restored cleanly.
- **Standardized Absolute Database Paths**: Explicitly initializes all sqlite databases using `config.DATA_DIR`, guaranteeing database integrity regardless of execution directory.
- **Image Studio Pro (Grok Imagine Architecture)**: Unified creative studio featuring text-to-image generation, a dedicated **Edit Canvas** for instruction-guided img2img & inpainting, and an asset **Library** gallery.
- **Direct Computer Storage Upload**: Upload any `.png`, `.jpg`, or `.webp` file from local storage via drag-and-drop or file picker with 25MB payload guard, automatic EXIF orientation stripping, and sRGB sanitization.
- **Dedicated Inpainting & ControlNet IP2P Pipelines**: True split model execution routing ControlNet models (`control_v11e_sd15_ip2p_fp16`, `control_v11p_sd15_inpaint_fp16`) through Forge `alwayson_scripts` and inpainting checkpoints through `/sdapi/v1/options`.
- **Multi-Reference Editing Deck (Up to 5 Reference Images)**: Dynamic reference image dock supporting simultaneous multi-style and composition conditioning dispatched to local ControlNet units.
- **Hardware-Aware GPU Scheduler & Media Task Queue**: Strict VRAM coordination preventing concurrent VRAM collisions between LLM reasoning and SD image synthesis on 6GB VRAM GPUs, backed by a FIFO media task queue (`/api/gpu/queue`).
- **Inpainting Canvas Mask Eraser & Undo/Redo**: Full interactive masking toolbar supporting white drawing, `destination-out` erasing, and complete `Undo`/`Redo` history stacks.
- **Magic Wand Semantic Segmentation**: One-click ADE20K semantic segmentation using ControlNet, converting scene objects into precision inpaint masks without manual drawing.
- **Background Removal (Isolated Transparent PNG)**: One-click subject segmentation that removes background with clean alpha transparency saved directly to the session asset tree.
- **Background Replacement**: Inverts subject masks, preserves the foreground object, and regenerates realistic new backgrounds from natural language prompts via localized inpainting.
- **Generative Outpainting (Aspect Ratio Expansion)**: Auto-pads images into target widescreen aspect ratios (e.g., 16:9) and generates seamless extended scenes using edge-matched diffusion.
- **Local Hardware-Accelerated Upscaler**: Integrated hardware super-resolution (`R-ESRGAN 4x+`, `SwinIR 4x`, `DAT x2`) with 2x one-click upscale directly on the canvas.
- **Per-Session Workspace State Persistence**: Automatic debounced auto-sync storing prompt drafts, selected models, denoise strength, steps, and brush size in SQLite `visual_sessions` across application reboots.
- **Grok-Style Visual Session Rail**: Independent visual sessions with 3-image miniature preview cards, allowing users to switch between editing canvases without losing work.
- **Complete Zero-Trace Deletion System**: Full user control to delete any individual conversation, Imagine visual session, or image asset. Permanent file unlinking (`Path.unlink()`) ensures zero residue remains on disk.
- **Durable Cognitive Memory Queue**: Sequential background worker queue with real-time status telemetry (`GET /api/memory/status`), preventing task interruption during shutdowns.
- **Persistent Asset Database (`image_studio.db`)**: Full SQLite catalog with enforced foreign keys (`PRAGMA foreign_keys = ON`) maintaining version lineage (Upload &rarr; Edit 1 &rarr; Edit 2), favorite flags, prompt metadata, and dimensions.
- **Next-Gen Command Center & Ambient HUD**: Hexagonal lattice ambient background and interactive Arc Reactor canvas responding to real-time CPU/GPU system load.

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
