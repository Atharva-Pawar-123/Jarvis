import os

EXCLUDE_DIRS = {'venv', '__pycache__', '.git', '.vscode', '.mypy_cache', 'models', 'data', 'logs', 'generated_images', 'tools', 'node_modules', 'dist', 'claude-code', 'claude-code-main', 'build', 'scratch'}
EXCLUDE_EXTS = {'.sqlite', '.onnx', '.tflite', '.json', '.jpg', '.png', '.mp3', '.wav', '.db', '.whl', '.7z', '.bin', '.safetensors', '.pt', '.pth'}

SUMMARY = """=========================================================
JARVIS 2.0 FULL CONTEXT & ARCHITECTURE DUMP
=========================================================

This file contains the full architectural overview, conversational context, and complete source code of the JARVIS 2.0 project.
You can use this file to feed a fresh LLM instance to immediately gain full context of the project.

=== 1. ARCHITECTURE OVERVIEW ===
JARVIS is a fully local, multimodal AI assistant designed to run on Windows, leveraging local LLMs via Ollama. 
Key capabilities include:
- Core LLM Engine: IntelligentLLMEngine (uses qwen2.5:7b for primary thinking, qwen2.5:1.5b for fast intent classification).
- Hybrid RAG Memory: Uses ChromaDB (Semantic) and BM25 (Keyword) with Reciprocal Rank Fusion (RRF) for long-term fact and conversation retrieval.
- Multi-Modal Vision: Uses deepface, pyautogui, and Ollama's vision models for screen describing and face detection.
- Voice I/O: Uses faster-whisper for speech-to-text, and Piper TTS for text-to-speech. OpenWakeWord handles hotword detection ("hey jarvis").
- Browser Automation: Uses Playwright/Selenium for web search and scraping.
- Local Automation: Uses pyautogui and os tools to open/close apps, change volume, edit clipboard, and manipulate files.
- Realtime HUD: A local FastAPI server provides a websocket connection to a browser-based HUD overlay, built with HTML/CSS/JS, displaying system stats, memory, agent thinking, and visualizations.
- Modular Tools: Web search, news fetching, weather fetching, email reading/sending, WhatsApp automation.

=== 2. PROJECT STRUCTURE ===
- main.py: The central orchestrator, initializing engines, tools, the ReAct agent, and the wake word listener.
- config.py: Centralized configuration and paths.
- modules/: Contains all tool definitions and core engines (llm, memory, vision, automation, browser, tts, stt, email, etc.)
- server/: FastAPI server logic for the HUD.
- hud/: Frontend files (index.html, style.css, script.js) for the UI overlay.

=== 3. SOURCE CODE ===
Below is the content of every relevant file in the project.
=========================================================

"""

def run():
    out_file = 'JARVIS_Full_Context.txt'
    with open(out_file, 'w', encoding='utf-8') as f:
        f.write(SUMMARY)
        
        for root, dirs, files in os.walk('.'):
            # Prune excluded directories immediately
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS and not any(part in EXCLUDE_DIRS for part in os.path.normpath(os.path.join(root, d)).split(os.sep))]
            
            for file in files:
                ext = os.path.splitext(file)[1].lower()
                if ext in EXCLUDE_EXTS:
                    continue
                if file in ['JARVIS_Full_Context.txt', 'generate_context.py', 'jarvis_data.sqlite']:
                    continue
                
                path = os.path.join(root, file)
                parts = set(os.path.normpath(path).split(os.sep))
                if parts.intersection(EXCLUDE_DIRS):
                    continue
                try:
                    with open(path, 'r', encoding='utf-8') as infile:
                        content = infile.read()
                        f.write(f"\\n{'='*60}\\n")
                        f.write(f"FILE: {path}\\n")
                        f.write(f"{'='*60}\\n")
                        f.write(content)
                        f.write("\\n\\n")
                except Exception as e:
                    f.write(f"\\n[Error reading file {path}: {e}]\\n")

if __name__ == '__main__':
    run()
    print("Context file generated successfully.")
