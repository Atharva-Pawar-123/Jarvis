# J.A.R.V.I.S. (Just A Rather Very Intelligent System) 🤖✨
### Fully Local, Autonomous, 100% Offline AI Assistant for Personal Hardware

---

## 📌 Project Overview

**JARVIS** is an autonomous, fully local, multimodal AI desktop assistant modeled after the iconic Iron Man persona (voiced in the calm, witty, and precise British cadence of Paul Bettany). Engineered specifically for local personal hardware (optimized for NVIDIA RTX 3050 6GB VRAM, 16GB RAM, Windows 10/11), JARVIS operates **completely offline with zero cloud API subscriptions, zero recurring costs, and total data privacy**.

With the **V2.1 Reliability & Production Hardening Sprint**, JARVIS evolves from a reactive assistant into an enterprise-grade desktop intelligence platform:
- **Unified Runtime Container (`JarvisRuntime`)**: Single-source-of-truth container holding all module singletons, eliminating fragmented module-level globals across FastAPI and the voice daemon.
- **Canonical Tool Protocol & Schema Validation**: Strongly typed Pydantic parameter schemas (`CanonicalTool`) providing exact contracts for LLM tool calling and self-documenting APIs.
- **Interactive Security Authorization Gate**: High-risk operations (code execution, emails, deletions) trigger interactive WebSocket approval cards with 45-second timeouts and in-memory session caches.
- **Hardened Subprocess Sandbox**: Sanitized environments stripping all API tokens, cloud credentials, and sensitive environment variables (`GMAIL_*`, `AWS_*`, `*SECRET*`, `*PASSWORD*`) with execution timeouts.
- **Restart-Surviving Task Manager**: Checkpointed state machine in SQLite with live `asyncio.Event` cancellation tokens and automatic recovery of interrupted tasks upon reboot.
- **Tactical Desktop HUD & Task Command Center**: Real-time circular meters for CPU, RAM, GPU VRAM & temperature, interactive 4-tier memory inspector (Working, Episodic, Semantic, Procedural), and background goal launcher.
- **Hardware-Aware GPU Scheduler**: Manages mutually exclusive execution between Qwen LLM reasoning and Stable Diffusion Forge image generation to eliminate CUDA Out-of-Memory crashes on 6GB VRAM GPUs.
- **Automated Regression Test Suite**: 61 comprehensive tests covering orchestrator reasoning, permissions, sandbox security, background tasks, and GPU scheduling.

---

## 🏛️ Core Architecture & Models

```
+─────────────────────────────────────────────────────────────────────────────+
|                         USER INTERFACE & ENTRYPOINTS                        |
|  - Desktop App: Electron + React 19 + TailwindCSS + Zustand + Framer Motion |
|    * 💬 Chat View (ChatGPT/Claude-style streaming & autonomous reasoning)   |
|    * 🎙️ Voice View (Push-to-talk Arc Reactor Orb, transcript, British TTS)   |
|    * 🎨 Image Studio (Local Forge SD + Pollinations AI with model selector) |
|    * 📊 HUD Dashboard (Real-time CPU, RAM, GPU VRAM & system telemetry)     |
|    * 🧠 Memory Inspector, Task Monitor, and Settings Configuration         |
|  - Voice Daemon: OpenWakeWord ("hey_jarvis") + faster-whisper + Piper TTS   |
+─────────────────────────────────────────────────────────────────────────────+
                                       │
                                       ▼
+─────────────────────────────────────────────────────────────────────────────+
|                         CENTRAL NERVOUS SYSTEM                              |
|  - Unified Agent Orchestrator: Goal decomposition, ReAct reasoning & tools  |
|  - server/api_server.py: FastAPI REST & Scoped WebSocket Server (Port 8080) |
|  - Persistent Task Engine: Checkpointed state machine in SQLite             |
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
| - llava:7b      |          | - SD WebUI Forge  |          | - MCP & Skills   |
+─────────────────+          +───────────────────+          +──────────────────+
```

### Models & Subsystems
- **Primary Reasoning (`qwen2.5:7b`)**: General conversational intelligence, multi-step goal decomposition, and ReAct agent tool calling.
- **Intent Classifier (`qwen2.5:1.5b`)**: Fast, deterministic intent extraction and slot-filling with history context.
- **Vision Engine (`llava:7b` / `moondream2`)**: Screen understanding, OCR via PyTesseract, and DeepFace emotion detection.
- **Hybrid Memory (`nomic-embed-text` + ChromaDB + BM25)**: Vector embeddings + lexical keywords fused via Reciprocal Rank Fusion (RRF).
- **Speech-to-Text (`faster-whisper` small on CUDA)**: Transcribes voice in ~0.04s with Silero VAD adaptive silence detection (~0.6s).
- **Text-to-Speech (Piper `en_GB-alan-medium.onnx`)**: Crisp British accent with ~50 ms chunked playback and instant interruption.
- **Image Generation (SD WebUI Forge + Pollinations AI)**: Multi-model suite featuring local Stable Diffusion Forge (DreamShaper 8 on CUDA with xFormers) alongside free cloud fallback via Pollinations AI.

---

## 🖥️ Modern Desktop Application (ChatGPT / Grok / Claude Experience)

The desktop app in `app/` is a unified Electron + React client:

1. **💬 Chat View (Default AI Chat)**:
   - Type messages directly to JARVIS and receive token-by-token streaming responses.
   - Formatted with Markdown, code highlighting, copy buttons, and multi-session conversation history.
   - Live status indicator displaying current agent reasoning steps (e.g. *Searching web*, *Reading file*, *Inspecting screen*).
   - Optional microphone dictation directly in the chat bar.

2. **🎙️ Voice Chat View**:
   - Dedicated voice conversation screen featuring the pulsating JARVIS Arc Reactor Orb.
   - Push-to-talk button (`Tap to speak` / `Tap to stop`).
   - Real-time audio waveform visualizer and full transcript display.
   - Toggle voice speech responses (Mute/Unmute TTS).

3. **🎨 Image Gen Studio**:
   - Model selector: choose between **Auto (Best Available)**, **DreamShaper 8 (Local SD)**, and **Pollinations AI (Cloud)**.
   - Prompt input supporting text typing (default) or voice dictation via microphone.
   - Advanced settings: negative prompt, inference steps slider, and aspect ratio / size presets (512×512, 512×768, 768×512, 768×768).
   - Gallery strip with full-resolution preview, prompt reuse, and direct PNG download.

4. **📊 HUD Dashboard & Task Monitor**:
   - Live system gauges for CPU, RAM, GPU VRAM usage, and temperatures.
   - Visual inspect panel for active background tasks, checkpoints, and execution progress.

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
*Runs on port 7860 with `--xformers` and `--always-offload-from-vram`. If Forge is offline, JARVIS automatically routes image generation to Pollinations AI.*

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
| **Autonomous Workflows** | Goal decomposition and multi-step background tasks | *"Research AI tools and prepare a report"*, *"Organize my week"* |
| **Voice Barge-In / Interruption** | Silences JARVIS mid-speech in ~50 ms | Say *"Hey Jarvis"* while he speaks, talk over him, or press **Escape** |
| **Local Image Generation** | Renders images via local Forge or Pollinations | *"Generate an image of an Iron Man helmet on marble"*, *"Create a picture of..."* |
| **Screen Vision & OCR** | Analyzes screen content or webcam feed | *"Describe my screen"*, *"Read the text on my screen"*, *"Look at webcam"* |
| **Autonomous Code Engine** | Authors & runs Python/PowerShell scripts safely | *"Write a python script to solve Fibonacci and run it"*, *"Execute code to..."* |
| **Windows Automation** | Opens/closes apps, inspects windows, screenshots | *"Open Notepad"*, *"Close Spotify"*, *"Focus Chrome"*, *"Take a screenshot"* |
| **System Diagnostics** | Real-time monitoring of CPU, RAM, & GPU | *"System status"*, *"Check GPU telemetry"* |
| **Web & Live Information** | Web scraping, live search, weather, news | *"Search the web for..."*, *"What's the weather in London?"*, *"Get top news"* |
| **4-Tier Cognitive Memory** | Semantic + BM25 fact storage & procedural habits | *"Remember that my favorite language is Python"*, *"Search memory for..."* |
| **Smart Reminders** | Background scheduler with spoken alarms | *"Set a reminder in 10 minutes to take a break"*, *"Remind me at 5 PM"* |
