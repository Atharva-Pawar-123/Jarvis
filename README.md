# J.A.R.V.I.S. (Just A Rather Very Intelligent System) 🤖✨
### Fully Local, Autonomous, 100% Offline AI Assistant for Personal Hardware (V2.3)

---

## 📌 Project Overview

**JARVIS** is an autonomous, fully local, multimodal AI desktop assistant modeled after the iconic Iron Man persona (voiced in the calm, witty, and precise British cadence of Paul Bettany). Engineered specifically for local personal hardware (optimized for NVIDIA RTX 3050 6GB VRAM, 16GB RAM, Windows 10/11), JARVIS operates **completely offline with zero cloud API subscriptions, zero recurring costs, and total data privacy**.

With the completion of the **V2.3 Reliability, Security & Next-Gen Command Center Sprint**, JARVIS delivers an enterprise-grade, self-correcting desktop intelligence platform:
- **Unified Runtime Container (`JarvisRuntime`)**: Single-source-of-truth application container holding all module singletons, eliminating fragmented module-level globals across FastAPI and the voice daemon.
- **Canonical Tool Protocol & Strict Schemas**: Strongly-typed Pydantic contracts (`CanonicalTool`) providing exact validation, execution timeouts with non-blocking thread shutdown, and self-documenting JSON schemas for LLM tool calling.
- **Interactive Security Authorization Gate**: High-risk actions (code execution, email sending, file deletion, system power) require session-bound cryptographic approval cards with expiration TTL and fresh re-authorizations for sensitive commands.
- **Hardened Subprocess Sandbox**: Sanitized subprocess environments stripping cloud and personal API tokens with 64-bit aligned Windows Job Object memory caps and strict repository path boundaries.
- **Restart-Surviving Task DAG Engine**: Checkpointed state machine in SQLite with live `asyncio.Event` cancellation tokens, dynamic subtask DAG tracking with parallel topological execution, and automatic recovery of interrupted tasks upon system reboot.
- **Next-Gen Command Center HUD**: Futuristic military/sci-fi command dashboard with live clock, central holographic 3D particle orb, agent status matrix, mission timeline, live intelligence feed, hardware gauges, constellation memory insights, and one-click voice dock.
- **Hardware-Aware GPU Scheduler**: Manages mutually exclusive execution between Qwen LLM reasoning, LLaVA vision, and Stable Diffusion Forge image generation to eliminate CUDA Out-of-Memory crashes on 6GB VRAM GPUs.
- **100% Offline Diffusion Studio**: Fully local generation powered strictly by SD WebUI Forge with hot-swapping checkpoints (DreamShaper 8, Realistic Vision V5.1, FLUX.1 Schnell) and adaptive parameters. Zero cloud dependencies.

---

## 🏛️ Core Architecture & Models

```
+─────────────────────────────────────────────────────────────────────────────+
|                         USER INTERFACE & ENTRYPOINTS                        |
|  - Desktop App: Electron + React 19 + TailwindCSS + Zustand + Lucide        |
|    * 🌌 Command Center HUD (Futuristic sci-fi dashboard, orb, mission feeds)|
|    * 💬 Chat View (ChatGPT/Claude-style streaming & autonomous reasoning)   |
|    * 🎙️ Voice View (Push-to-talk Arc Reactor Orb, transcript, British TTS)   |
|    * 🎨 Image Studio (100% Local Forge SD with dynamic model selector)      |
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
- **Vision Engine (`llava:7b` / `moondream2`)**: Screen understanding, OCR via PyTesseract, and DeepFace emotion detection.
- **Hybrid Memory (`nomic-embed-text` + ChromaDB + BM25)**: Vector embeddings + lexical keywords fused via Reciprocal Rank Fusion (RRF).
- **Speech-to-Text (`faster-whisper` small on CUDA)**: Transcribes voice in ~0.04s with Silero VAD adaptive silence detection (~0.6s).
- **Text-to-Speech (Piper `en_GB-alan-medium.onnx`)**: Crisp British accent with ~50 ms chunked playback and instant interruption.
- **Image Generation (Local SD WebUI Forge on GPU)**: Multi-model suite featuring local Stable Diffusion Forge (DreamShaper 8, Realistic Vision V5.1, FLUX.1 Schnell) running directly on the NVIDIA RTX GPU. 100% offline with zero cloud dependencies.

---

## 🖥️ Modern Desktop Application (Futuristic Command Center HUD Experience)

The desktop app in `app/` is a unified Electron + React client:

1. **🌌 Command Center HUD (Default Landing Dashboard)**:
   - Central rotating 3D holographic wireframe orb with particle nebula and `JARVIS AI CORE v3.0.0` typography.
   - Top status header with live digital clock, date, glowing `SYSTEM STATUS: OPTIMAL` badge, search console, and Operator Commander card.
   - AI Core Overview with live states for Core, Memory, Voice, Agents, LLMs, and System.
   - Live Intelligence Feed prioritizing alerts with severity color coding (`INFO`, `WARN`, `TIP`, `LIVE`).
   - Active Agents matrix with live animated sparkline waveforms for Coding, Research, Memory, Browser, Task, and System agents.
   - Mission Timeline with scheduled daily events, completion status, and quick command buttons.
   - Real-time hardware telemetry circular SVG dials for CPU, RAM, and Disk.
   - Constellation Memory Insights displaying memory volume, session turn counts, and tool invocations.
   - Multi-provider LLM status grid and glowing bottom **`TALK TO JARVIS`** action dock with Executive Briefing.

2. **💬 Chat View**:
   - Type messages directly to JARVIS and receive token-by-token streaming responses.
   - Formatted with Markdown, code highlighting, copy buttons, and multi-session conversation history.
   - Live collapsible **"Thinking & Reasoning"** status indicator displaying step-by-step agent planning.
   - Interactive amber **Security Authorization Card** for one-click human-in-the-loop approvals.
   - Optional microphone dictation directly in the chat bar.

3. **🎙️ Voice Chat View**:
   - Dedicated voice conversation screen featuring the pulsating JARVIS Arc Reactor Orb.
   - Push-to-talk button (`Tap to speak` / `Tap to stop`).
   - Real-time audio waveform visualizer and full transcript display.
   - Toggle voice speech responses (Mute/Unmute TTS).

4. **🎨 Image Gen Studio**:
   - Model selector: choose explicitly between local models: **DreamShaper 8 (SD 1.5)**, **Realistic Vision V5.1 (SD 1.5 Photorealistic)**, or **FLUX.1 Schnell** — no automatic fallbacks, direct user control.
   - Prompt input supporting text typing (default) or voice dictation via microphone.
   - Advanced settings: negative prompt, inference steps slider, and aspect ratio / size presets (512×512, 512×768, 768×512, 1024×1024).
   - Gallery strip with full-resolution preview, prompt reuse, and direct PNG download.

5. **📊 HUD Dashboard**:
   - Live circular telemetry meters for CPU load, RAM usage, GPU VRAM allocation, and core temperatures.
   - Status indicators showing active VRAM consumers (`llm` vs `forge`), uptime, and active sessions.

6. **📋 Task Command Center**:
   - Background autonomous goal launcher with subtask estimation and DAG graph tracking.
   - Real-time task status pills (`QUEUED`, `RUNNING`, `COMPLETED`, `CANCELLED`, `INTERRUPTED`).
   - Live progress bars and instant task cancellation buttons.

7. **🧠 4-Tier Memory Inspector**:
   - **Working Memory**: Active session cache, current constraints, and past episode retrieval.
   - **Episodic Memory**: Chronological action timeline and interaction history.
   - **Semantic Memory**: Knowledge base search, interactive fact insertion, and memory deletion.
   - **Procedural Memory**: Learned habits, automated execution patterns, and routines.

---

## 🚀 How to Run the Project

### 1. Prerequisites Checklist
1. **Ollama**:
   ```powershell
   ollama serve
   ollama pull qwen2.5:7b
   ollama pull qwen2.5:1.5b
   ollama pull nomic-embed-text
   ```
2. **Virtual Environment**:
   ```powershell
   cd D:\JARVIS
   .\venv\Scripts\Activate.ps1
   ```

---

### 2. Running the Modern Desktop App (Recommended)
Launch the complete desktop application with a single command:
```powershell
cd D:\JARVIS\app
npm run electron:dev
```
*Electron will automatically start the backend server (`server/api_server.py`), poll until it is healthy, launch the Vite UI, and open the desktop window.*

---

### 3. Running in Browser Mode (Alternative)
```powershell
# Terminal 1: Backend
cd D:\JARVIS
.\venv\Scripts\Activate.ps1
python -m server.api_server

# Terminal 2: Frontend
cd D:\JARVIS\app
npm run dev
```
Open `http://localhost:5173` in your browser.

---

### 4. Running the Voice Daemon (`main.py`)
To use JARVIS purely as a voice-driven background assistant with wake word listening:
```powershell
cd D:\JARVIS
.\venv\Scripts\Activate.ps1
python main.py
```
*JARVIS will initialize all subsystems and speak: "JARVIS online and ready, sir."*

---

### 5. Running Local Image Generation (Forge API)
```powershell
cd D:\JARVIS\tools\forge
.\start_forge_api.bat
```
*Runs on port 7860 with `--xformers` and `--always-offload-from-vram`. Fully local-first and offline.*

---

### 6. Running the Automated Test Suite (Pytest)
To run the full V2.1 regression test suite (61 tests covering orchestrator, permissions, sandbox, tasks, and GPU scheduler):
```powershell
cd D:\JARVIS
.\venv\Scripts\Activate.ps1
python -m pytest tests/v2/ -v
```

---

## 🌟 Features & Activation Commands

| Capability | What It Does | How to Activate (Voice or Typed) |
|---|---|---|
| **Text Chat** | Conversational reasoning like ChatGPT/Claude | Type message in the **Chat** tab and press `Enter` |
| **Dedicated Voice Chat** | Full-screen push-to-talk orb with transcript | Click the **Voice Chat** tab in the sidebar |
| **Image Studio** | Multi-model image generation with gallery & presets | Click the **Image Gen** tab in the sidebar |
| **Tactical HUD** | Live CPU, RAM, GPU VRAM & thermal gauges | Click the **HUD** tab in the sidebar |
| **Task Center** | Launch, monitor, and cancel long-running goals | Click the **Tasks** tab in the sidebar |
| **4-Tier Memory Inspector** | Search, add, or clear working/semantic/episodic memory | Click the **Memory** tab in the sidebar |
| **Autonomous Workflows** | Goal decomposition and multi-step background tasks | *"Research AI tools and prepare a report"*, *"Organize my week"* |
| **Voice Barge-In / Interruption** | Silences JARVIS mid-speech in ~50 ms | Say *"Hey Jarvis"* while he speaks, talk over him, or press **Escape** |
| **Local Image Generation** | Renders images via local SD WebUI Forge on GPU | *"Generate an image of an Iron Man helmet on marble"*, *"Create a picture of..."* |
| **Screen Vision & OCR** | Analyzes screen content or webcam feed | *"Describe my screen"*, *"Read the text on my screen"*, *"Look at webcam"* |
| **Autonomous Code Engine** | Authors & runs Python scripts in hardened sandbox | *"Write a python script to solve Fibonacci and run it"*, *"Execute code to..."* |
| **Windows Automation** | Opens/closes apps, inspects windows, screenshots | *"Open Notepad"*, *"Close Spotify"*, *"Focus Chrome"*, *"Take a screenshot"* |
| **System Diagnostics** | Real-time monitoring of CPU, RAM, & GPU | *"System status"*, *"Check GPU telemetry"* |
| **Web & Live Information** | Web scraping, live search, weather, news | *"Search the web for..."*, *"What's the weather in London?"*, *"Get top news"* |
| **Smart Reminders** | Background scheduler with spoken alarms | *"Set a reminder in 10 minutes to take a break"*, *"Remind me at 5 PM"* |
