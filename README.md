# J.A.R.V.I.S. (Just A Rather Very Intelligent System) 🤖✨
### 100% Offline, Private, Zero-Cost AI Assistant for Personal Hardware

---

## 📌 Project Overview

**JARVIS** is an autonomous, fully local, multimodal AI desktop assistant modeled after the Iron Man persona (Paul Bettany). Engineered specifically for personal hardware (optimized for NVIDIA RTX 3050 6GB VRAM, 16GB RAM, Windows 10/11), JARVIS operates **completely offline with zero cloud API subscriptions, zero recurring costs, and complete privacy**.

JARVIS coordinates speech recognition, conversational intelligence, reasoning, vision, system automation, and high-speed local image generation through a modern multi-tab desktop app (providing a native ChatGPT / Claude / Grok-style experience).

---

## 🏛️ Core Architecture & Models

```
+─────────────────────────────────────────────────────────────────────────────+
|                         USER INTERFACE & ENTRYPOINTS                        |
|  - Desktop App: Electron + React 19 + TailwindCSS + Zustand + Framer Motion |
|    * 💬 Chat View (ChatGPT/Claude style text messaging & reasoning)         |
|    * 🎙️ Voice View (Push-to-talk orb with transcript & British TTS)         |
|    * 🎨 Image Studio (Local Forge SD + Pollinations AI with model selector) |
|    * 📊 HUD Dashboard (Real-time telemetry, GPU VRAM & system meters)       |
|    * 🧠 Memory Inspector & Settings Configuration                           |
|  - Voice Daemon: OpenWakeWord ("hey_jarvis") + faster-whisper + Piper TTS   |
|  - Classic Browser HUD: HTML5 / WebSocket audio orb & telemetry             |
+─────────────────────────────────────────────────────────────────────────────+
                                       │
                                       ▼
+─────────────────────────────────────────────────────────────────────────────+
|                         CENTRAL NERVOUS SYSTEM                              |
|  - main.py: CLI Orchestrator, Hotword Loop, Audio & Execution Dispatch      |
|  - server/api_server.py: FastAPI REST & WebSocket Server (Port 8080)        |
+─────────────────────────────────────────────────────────────────────────────+
                                       │
        ┌──────────────────────────────┼──────────────────────────────┐
        ▼                              ▼                              ▼
+─────────────────+          +───────────────────+          +──────────────────+
| COGNITIVE CORE  |          |   SENSORY ENGINE  |          | AUTOMATION SUITE |
| (Local Ollama)  |          |   (Audio & Vision)|          | (System & Tools) |
| - qwen2.5:7b    |          | - faster-whisper  |          | - automation.py  |
| - qwen2.5:1.5b  |          | - Piper TTS       |          | - code_engine.py |
| - nomic-embed   |          | - OpenWakeWord    |          | - scheduler.py   |
| - llava:7b      |          | - Silero VAD      |          | - browser.py     |
|                 |          | - SD WebUI Forge  |          | - web_search.py  |
+─────────────────+          +───────────────────+          +──────────────────+
```

### Models & Tasks
- **Primary Thinking (`qwen2.5:7b`)**: General conversational intelligence, multi-turn reasoning, and tool synthesis.
- **Intent Classifier (`qwen2.5:1.5b`)**: Fast, deterministic intent extraction and slot-filling with history context.
- **Code Engine (`qwen2.5:7b`)**: Script synthesis and autonomous Python/PowerShell execution in a secure sandbox.
- **Vision Engine (`llava:7b` / `moondream2`)**: Screen understanding, OCR via PyTesseract, and DeepFace emotion detection.
- **Hybrid Memory (`nomic-embed-text` + ChromaDB + BM25)**: Vector embeddings + lexical keywords fused via Reciprocal Rank Fusion (RRF).
- **Speech-to-Text (`faster-whisper` small on CUDA)**: Transcribes voice in ~0.04s with Silero VAD adaptive silence detection (~0.6s).
- **Text-to-Speech (Piper `en_GB-alan-medium.onnx`)**: Crisp British accent with ~50 ms chunked playback and instant interruption.
- **Image Generation (SD WebUI Forge + Pollinations AI)**: Multi-model suite featuring local Stable Diffusion Forge (DreamShaper 8 on CUDA with xFormers) alongside free cloud fallback via Pollinations AI.

---

## 🖥️ Modern Desktop Application (ChatGPT / Grok Experience)

The desktop app in `app/` is a unified Electron + React interface:

1. **💬 Chat View (Default AI Chat)**:
   - Type messages directly to JARVIS and receive token-by-token streaming responses.
   - Formatted with Markdown, code highlighting, copy buttons, and multi-session conversation history.
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
Launch the complete desktop application with one command:
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

## 🌟 Features & Activation Commands

| Capability | What It Does | How to Activate (Voice or Typed) |
|---|---|---|
| **Text Chat** | Conversational reasoning like ChatGPT/Claude | Type message in the **Chat** tab and press `Enter` |
| **Dedicated Voice Chat** | Full-screen push-to-talk orb with transcript | Click the **Voice Chat** tab in the sidebar |
| **Image Studio** | Multi-model image generation with gallery & presets | Click the **Image Gen** tab in the sidebar |
| **Voice Barge-In / Interruption** | Silences JARVIS mid-speech in ~50 ms | Say *"Hey Jarvis"* while he speaks, talk over him, or press **Escape** |
| **Local Image Generation** | Renders images via local Forge or Pollinations | *"Generate an image of an Iron Man helmet on marble"*, *"Create a picture of..."* |
| **Screen Vision & OCR** | Analyzes screen content or webcam feed | *"Describe my screen"*, *"Read the text on my screen"*, *"Look at webcam"* |
| **Autonomous Code Engine** | Authors & runs Python/PowerShell scripts | *"Write a python script to solve Fibonacci and run it"*, *"Execute code to..."* |
| **Windows Automation** | Opens/closes apps, adjusts volume, screenshots | *"Open Notepad"*, *"Close Spotify"*, *"Volume up"*, *"Mute"*, *"Take a screenshot"* |
| **System Diagnostics** | Real-time monitoring of CPU, RAM, & Disk | *"System status"*, *"Check system diagnostics"* |
| **Web & Live Information** | Web scraping, live search, weather, news | *"Search the web for..."*, *"What's the weather in London?"*, *"Get top news"* |
| **Hybrid RAG Memory** | Semantic + BM25 long-term fact storage | *"Remember that my favorite language is Python"*, *"Search memory for..."*, *"Clear memory"* |
| **Document Ingestion** | Reads and embeds PDF, DOCX, TXT files | *"Ingest document D:\path\to\document.pdf"* |
| **Smart Reminders** | Background scheduler with spoken alarms | *"Set a reminder in 10 minutes to take a break"*, *"Remind me at 5 PM"* |
| **ReAct & UltraPlan** | Complex multi-step reasoning and background tasks | *"Check the weather, summarize it, and save to a file"* |
