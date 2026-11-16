"""
server/api_server.py — JARVIS FastAPI Backend
==============================================
The central nervous system for the JARVIS desktop application.
Bridges the React/Electron frontend with all Python JARVIS modules
via REST endpoints and real-time WebSocket streaming.
"""

import sys
import os
import json
import uuid
import asyncio
import logging
import time
import tempfile
import base64
from pathlib import Path
from datetime import datetime
from typing import Optional, List

from fastapi import (
    FastAPI, WebSocket, WebSocketDisconnect, HTTPException,
    UploadFile, File, Header
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import uvicorn

# ── Add JARVIS root to path ────────────────────────────────────────────
JARVIS_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(JARVIS_ROOT))

import config
from modules.llm import IntelligentLLMEngine
from modules.stt import SpeechToText
from modules.tts import StreamingTextToSpeech
from modules.intent import DualModelIntentClassifier
from modules.long_term_memory import HybridRAGMemory
from modules.automation import AutomationEngine
from modules.email_handler import EmailHandler
from modules.vision import VisionEngine
from modules.code_engine import CodeEngine
from modules.image_gen import ImageGenerationEngine
from modules.security.permission_engine import PermissionEngine, ActionCategory
from modules.agent.tool_registry import StructuredToolRegistry
from modules.agent.orchestrator import UnifiedAgentOrchestrator
from modules.tasks.task_manager import PersistentTaskManager
from modules.cognitive_memory import FourTierMemorySystem
from modules.skills.registry import DynamicSkillRegistry
from modules.mcp.manager import PluginManager
from modules.gpu_scheduler import GPUScheduler
from modules.computer_use import WindowsComputerUse, PlaywrightBrowserAgent
from modules.autonomous_workflow import AutonomousWorkflowEngine
from server.session_db import SessionDatabase
from server.api_keys import APIKeyManager
from server.websocket_manager import ConnectionManager

logger = logging.getLogger(__name__)

# ── App Setup ──────────────────────────────────────────────────────────
app = FastAPI(
    title="JARVIS API",
    version="3.0",
    description="JARVIS Local AI Backend — Zero Cloud Dependencies"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Global State ───────────────────────────────────────────────────────
START_TIME = time.time()

# Module instances (initialized lazily in startup)
manager: ConnectionManager = ConnectionManager()
key_mgr: APIKeyManager = APIKeyManager()
session_db: SessionDatabase = SessionDatabase()
permission_engine: PermissionEngine = PermissionEngine()
tool_registry: StructuredToolRegistry = StructuredToolRegistry()
task_manager: PersistentTaskManager = PersistentTaskManager()
skill_registry: DynamicSkillRegistry = DynamicSkillRegistry()
mcp_manager: PluginManager = PluginManager()
gpu_scheduler: GPUScheduler = GPUScheduler()
computer_use: WindowsComputerUse = WindowsComputerUse()
browser_agent: PlaywrightBrowserAgent = PlaywrightBrowserAgent()
workflow_engine: AutonomousWorkflowEngine = None
four_tier_memory: FourTierMemorySystem = None
orchestrator: UnifiedAgentOrchestrator = None
llm: IntelligentLLMEngine = None
tts: StreamingTextToSpeech = None
stt: SpeechToText = None
intent: DualModelIntentClassifier = None
memory: HybridRAGMemory = None
vision: VisionEngine = None
automation: AutomationEngine = None
email_h: EmailHandler = None
code_e: CodeEngine = None
image_gen: ImageGenerationEngine = None

# Settings file
SETTINGS_FILE = config.DATA_DIR / "user_settings.json"


# ── Pydantic Models ───────────────────────────────────────────────────
class MessageRequest(BaseModel):
    session_id: str
    content: str
    use_voice: bool = False

class NewSessionRequest(BaseModel):
    title: Optional[str] = "New conversation"

class MemoryAddRequest(BaseModel):
    fact: str
    category: Optional[str] = "general"

class APIKeyCreateRequest(BaseModel):
    name: str
    permissions: List[str] = ["chat", "tools"]
    rate_limit: int = 100

class SettingsUpdateRequest(BaseModel):
    primary_model: Optional[str] = None
    voice_speed: Optional[float] = None
    theme: Optional[str] = None
    wake_word_enabled: Optional[bool] = None

class CommandRequest(BaseModel):
    command: str
    session_id: str

class ImageGenRequest(BaseModel):
    prompt: str
    negative_prompt: Optional[str] = ""
    model: Optional[str] = "auto"
    steps: Optional[int] = 20
    width: Optional[int] = 512
    height: Optional[int] = 512
    enhance_prompt: Optional[bool] = True


# ── Helper Functions ──────────────────────────────────────────────────
def _load_settings() -> dict:
    if SETTINGS_FILE.exists():
        return json.loads(SETTINGS_FILE.read_text())
    return {
        "primary_model": config.PRIMARY_MODEL,
        "fast_model": config.FAST_MODEL,
        "coder_model": config.CODER_MODEL,
        "voice_speed": 1.0,
        "theme": "work",
        "wake_word_enabled": True,
    }

def _save_settings(settings: dict):
    SETTINGS_FILE.write_text(json.dumps(settings, indent=2))


def _build_messages(session_id: str, user_content: str,
                    memory_context: str = "") -> list:
    """Build the message list for the LLM from persistent conversation history."""
    msgs = [{"role": "system", "content": config.JARVIS_SYSTEM_PROMPT}]

    if memory_context:
        msgs.append({
            "role": "system",
            "content": f"Relevant memory context:\n{memory_context}"
        })

    # Add conversation history from SQLite
    sess = session_db.get_session(session_id)
    if sess and sess.get("messages"):
        for m in sess["messages"][-config.MAX_HISTORY_TURNS * 2:]:
            role = "user" if m["role"] == "user" else "assistant"
            msgs.append({"role": role, "content": m["content"]})

    msgs.append({"role": "user", "content": user_content})
    return msgs


def _ensure_session(session_id: str) -> str:
    """Create session in SQLite if it doesn't exist. Return session_id."""
    session_db.create_session(session_id)
    return session_id


# ═══════════════════════════════════════════════════════════════════════
# REST ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════

# ── Health ─────────────────────────────────────────────────────────────
@app.get("/health")
@app.get("/api/health")
async def health():
    ollama_ok = False
    try:
        import ollama as _ollama
        _ollama.list()
        ollama_ok = True
    except Exception:
        pass
    return {
        "status": "ok",
        "version": "3.1",
        "ollama": ollama_ok,
        "uptime_seconds": int(time.time() - START_TIME),
    }


# ── Models ─────────────────────────────────────────────────────────────
@app.get("/api/models")
async def list_models():
    try:
        import ollama as _ollama
        result = _ollama.list()
        models = []
        for m in result.get("models", []):
            name = m.get("name", m.get("model", "unknown"))
            size_bytes = m.get("size", 0)
            models.append({
                "name": name,
                "size_gb": round(size_bytes / (1024**3), 1),
                "active": name in [
                    config.PRIMARY_MODEL, config.FAST_MODEL,
                    config.CODER_MODEL
                ],
            })
        return {"models": models}
    except Exception as e:
        return {"models": [], "error": str(e)}


# ── Sessions ──────────────────────────────────────────────────────────
@app.post("/api/sessions/new")
async def create_session(req: NewSessionRequest):
    sid = str(uuid.uuid4())
    res = session_db.create_session(sid, req.title or "New conversation")
    return res


@app.get("/api/sessions")
async def list_sessions():
    return session_db.list_sessions()


@app.get("/api/sessions/{session_id}")
async def get_session(session_id: str):
    sess = session_db.get_session(session_id)
    if not sess:
        raise HTTPException(404, "Session not found")
    return sess


@app.delete("/api/sessions/{session_id}")
async def delete_session(session_id: str):
    session_db.delete_session(session_id)
    return {"deleted": session_id}


# ── Autonomous Workflow Endpoints ────────────────────────────────────
class AutonomousGoalRequest(BaseModel):
    goal: str
    title: Optional[str] = None

@app.post("/api/workflows/goal")
async def start_autonomous_goal(req: AutonomousGoalRequest):
    if not workflow_engine:
        raise HTTPException(500, "Autonomous Workflow Engine not ready.")
    task_id = await workflow_engine.start_autonomous_goal(req.goal, req.title)
    return {"task_id": task_id, "status": "QUEUED", "goal": req.goal}


# ── Computer Use & Telemetry Endpoints ───────────────────────────────
@app.get("/api/windows/active")
async def get_active_window():
    return computer_use.get_active_window()


@app.get("/api/windows/list")
async def list_open_windows():
    return {"windows": computer_use.list_open_windows()}


@app.post("/api/windows/focus")
async def focus_window(query: str):
    ok = computer_use.focus_window(query)
    return {"success": ok}


@app.get("/api/gpu/telemetry")
async def get_gpu_telemetry():
    return gpu_scheduler.get_gpu_telemetry()


# ── Skills & MCP Endpoints ───────────────────────────────────────────
@app.get("/api/skills")
async def list_skills():
    return {"skills": skill_registry.list_loaded_skills()}


@app.get("/api/mcp/servers")
async def list_mcp_servers():
    return {
        "servers": list(mcp_manager.clients.keys()),
        "tools": [t.to_llm_schema() for t in mcp_manager._all_tools]
    }


# ── Background Tasks Endpoints ───────────────────────────────────────
@app.get("/api/tasks")
async def list_tasks():
    return {"tasks": task_manager.list_tasks()}


@app.get("/api/tasks/{task_id}")
async def get_task(task_id: str):
    t = task_manager.get_task(task_id)
    if not t:
        raise HTTPException(404, "Task not found")
    return t


@app.post("/api/tasks/{task_id}/cancel")
async def cancel_task(task_id: str):
    task_manager.cancel_task(task_id)
    return {"cancelled": task_id}


# ── Chat (Main Endpoint) ─────────────────────────────────────────────
@app.post("/api/message")
async def send_message(req: MessageRequest):
    start_t = time.time()
    sid = _ensure_session(req.session_id)

    # 1. Append user message to SQLite
    session_db.add_message(sid, "user", req.content)

    # 2. Classify intent
    classified = await asyncio.to_thread(intent.classify, req.content)
    intent_name = classified.get("intent", "chat")

    # 3. Check Security / Permission Gate for classified action
    if intent_name in (ActionCategory.SEND_EMAIL, ActionCategory.SEND_WHATSAPP, ActionCategory.DELETE_FILE, ActionCategory.SYSTEM_SHUTDOWN):
        authorized, reason = await permission_engine.verify_and_authorize(intent_name, {"query": req.content})
        if not authorized:
            refusal_response = f"I require your explicit authorization to proceed with {intent_name.replace('_', ' ')}, sir. Action was not executed."
            session_db.add_message(sid, "jarvis", refusal_response)
            return {
                "response": refusal_response,
                "intent": intent_name,
                "session_id": sid,
                "tokens_used": len(refusal_response) // 4,
                "latency_ms": int((time.time() - start_t) * 1000),
            }

    # 4. Get memory context
    ctx = ""
    try:
        ctx = await asyncio.to_thread(memory.get_relevant_context, req.content)
    except Exception as e:
        logger.warning(f"Memory retrieval failed: {e}")

    # 5. Build message list
    messages = _build_messages(sid, req.content, ctx)

    # 6. Generate response via Unified Agent Orchestrator
    response_text = ""
    try:
        sess = session_db.get_session(sid)
        history = sess.get("messages", [])[:-1] if sess else []

        if orchestrator:
            response_text = await orchestrator.execute_task(
                query=req.content,
                conversation_history=history,
                step_callback=lambda step: manager.send_to_session(sid, {"type": "agent_step", "step": step})
            )
        else:
            response_text = await asyncio.to_thread(
                llm.generate, messages, False
            )
    except Exception as e:
        logger.error(f"Orchestrator generation failed: {e}", exc_info=True)
        response_text = "I'm experiencing a temporary issue with my reasoning engine, sir. Please try again."

    # 7. Append JARVIS response to SQLite
    session_db.add_message(sid, "jarvis", response_text)

    # 8. Auto-title first message
    sess = session_db.get_session(sid)
    if sess and len(sess.get("messages", [])) == 2:
        try:
            title = await asyncio.to_thread(
                llm.generate,
                [{"role": "user", "content":
                  f"Give this conversation a short 4-word title: {req.content}"}],
                False, False, config.FAST_MODEL
            )
            clean_title = title.strip().strip('"').strip("'")[:50]
            session_db.update_title(sid, clean_title)
        except Exception:
            pass

    # 8. Extract facts in background
    try:
        asyncio.get_event_loop().run_in_executor(
            None, memory.extract_and_store_facts, req.content, response_text
        )
    except Exception:
        pass

    # 9. TTS if requested
    if req.use_voice:
        try:
            asyncio.get_event_loop().run_in_executor(
                None, tts.speak, response_text
            )
        except Exception:
            pass

    latency = int((time.time() - start_t) * 1000)
    return {
        "response": response_text,
        "intent": intent_name,
        "session_id": sid,
        "tokens_used": len(response_text) // 4,
        "latency_ms": latency,
    }


# ── Quick Command (no conversation storage) ──────────────────────────
@app.post("/api/command")
async def quick_command(req: CommandRequest):
    classified = await asyncio.to_thread(intent.classify, req.command)
    messages = _build_messages(req.session_id, req.command)
    response = await asyncio.to_thread(llm.generate, messages, False)
    return {
        "response": response,
        "intent": classified.get("intent", "chat"),
    }


# ── Memory Endpoints ─────────────────────────────────────────────────
@app.get("/api/memory/facts")
async def get_facts():
    try:
        results = memory.facts_col.get(include=["documents", "metadatas"])
        facts = []
        for i, doc in enumerate(results.get("documents", [])):
            meta = results.get("metadatas", [{}])[i] if results.get("metadatas") else {}
            facts.append({
                "id": results["ids"][i],
                "text": doc,
                "category": meta.get("category", "general"),
                "timestamp": meta.get("timestamp", ""),
                "usage_count": meta.get("usage_count", 0),
            })
        return {"facts": facts}
    except Exception as e:
        logger.error(f"Failed to retrieve facts: {e}")
        return {"facts": [], "error": str(e)}


@app.get("/api/memory/search")
async def search_memory(q: str):
    try:
        results = await asyncio.to_thread(memory.get_relevant_context, q)
        return {"results": [{"text": results, "score": 1.0, "source": "hybrid"}]}
    except Exception as e:
        return {"results": [], "error": str(e)}


@app.post("/api/memory/add")
async def add_memory(req: MemoryAddRequest):
    try:
        await asyncio.to_thread(
            memory.add_fact, req.fact,
            {"category": req.category, "timestamp": datetime.now().isoformat()}
        )
        return {"added": req.fact}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.delete("/api/memory/{fact_id}")
async def delete_memory(fact_id: str):
    try:
        memory.facts_col.delete(ids=[fact_id])
        return {"deleted": fact_id}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/memory/clear")
async def clear_memory(x_confirm: Optional[str] = Header(None)):
    if x_confirm != "CLEAR_ALL_MEMORY":
        raise HTTPException(403, "Missing confirmation header: X-Confirm: CLEAR_ALL_MEMORY")
    try:
        memory.facts_col.delete(where={})
        memory.convs_col.delete(where={})
        memory.docs_col.delete(where={})
        return {"cleared": True}
    except Exception as e:
        raise HTTPException(500, str(e))


# ── Image Generation Endpoints ───────────────────────────────────────
@app.get("/api/image/models")
async def list_image_models():
    """List available image generation models (Local Forge + Pollinations)."""
    models = [
        {
            "id": "auto",
            "name": "Auto (Best Available)",
            "source": "auto",
            "description": "Local SD Forge if running, otherwise free cloud Pollinations AI"
        },
        {
            "id": "pollinations",
            "name": "Pollinations AI (Cloud)",
            "source": "pollinations",
            "description": "Free cloud generation — No local GPU load, high aesthetic quality"
        }
    ]

    # Check local Forge models if available
    try:
        import requests
        forge_url = getattr(config, "SD_LOCAL_URL", "http://127.0.0.1:7860")
        resp = requests.get(f"{forge_url}/sdapi/v1/sd-models", timeout=1.5)
        if resp.status_code == 200:
            for item in resp.json():
                title = item.get("title") or item.get("model_name") or "Local Model"
                models.insert(1, {
                    "id": f"local:{title}",
                    "name": f"{title} (Local SD)",
                    "source": "forge",
                    "description": f"Local Forge checkpoint: {item.get('filename', title)}"
                })
    except Exception:
        # If Forge offline, still show local DreamShaper option
        models.insert(1, {
            "id": "local",
            "name": "DreamShaper 8 (Local SD)",
            "source": "forge",
            "description": "Local SD Forge on GPU (auto-starts if available)"
        })

    return {"models": models}


@app.post("/api/image/generate")
async def generate_image_api(req: ImageGenRequest):
    """Generate image and return as base64 data for the UI."""
    if not image_gen:
        raise HTTPException(500, "Image generation engine not initialized.")

    working_prompt = req.prompt
    enhanced_prompt = req.prompt
    if req.enhance_prompt and llm:
        try:
            enhanced_prompt = await asyncio.to_thread(image_gen.enhance_prompt, req.prompt, llm)
            working_prompt = enhanced_prompt
        except Exception:
            working_prompt = req.prompt

    img_bytes = None
    source = "Unknown"

    # Select generation route based on model parameter
    model_choice = req.model or "auto"

    if model_choice == "pollinations":
        # Force cloud Pollinations
        img_bytes, source = await asyncio.to_thread(_generate_pollinations_direct, working_prompt)
    elif model_choice == "local" or model_choice.startswith("local:"):
        # Force local
        img_bytes = await asyncio.to_thread(
            image_gen._generate_local,
            working_prompt,
            req.negative_prompt or "",
            req.steps or 20,
            req.width or 512,
            req.height or 512
        )
        source = "Local Stable Diffusion" if img_bytes else None
    else:
        # Auto: try local first, fallback to Pollinations
        img_bytes = await asyncio.to_thread(
            image_gen._generate_local,
            working_prompt,
            req.negative_prompt or "",
            req.steps or 20,
            req.width or 512,
            req.height or 512
        )
        if img_bytes:
            source = "Local Stable Diffusion"
        else:
            img_bytes, source = await asyncio.to_thread(_generate_pollinations_direct, working_prompt)

    if not img_bytes:
        raise HTTPException(500, "Image generation failed on all available engines.")

    # Save to disk
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    filename = f"gen_{timestamp}.png"
    filepath = image_gen.save_dir / filename
    try:
        with open(filepath, "wb") as f:
            f.write(img_bytes)
    except Exception as e:
        logger.warning(f"Failed to save generated image to disk: {e}")

    img_b64 = base64.b64encode(img_bytes).decode("utf-8")
    return {
        "image_base64": img_b64,
        "source": source,
        "filepath": str(filepath),
        "prompt": req.prompt,
        "enhanced_prompt": enhanced_prompt
    }


def _generate_pollinations_direct(prompt: str):
    """Direct helper for Pollinations AI request."""
    import urllib.parse
    import requests
    encoded = urllib.parse.quote(prompt.strip())
    url = f"https://image.pollinations.ai/prompt/{encoded}?nologo=true&model=turbo"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    for attempt in range(3):
        try:
            resp = requests.get(url, headers=headers, timeout=60)
            if resp.status_code == 200 and resp.content:
                return resp.content, "Pollinations AI (Cloud)"
            elif resp.status_code in (402, 429, 503):
                time.sleep(4)
        except Exception as e:
            logger.warning(f"Pollinations attempt {attempt+1} failed: {e}")
            time.sleep(2)
    return None, "Pollinations AI (Failed)"


# ── Vision Endpoints ─────────────────────────────────────────────────
@app.get("/api/vision/screenshot")
async def take_screenshot():
    try:
        import pyautogui
        import io
        img = pyautogui.screenshot()
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        img_b64 = base64.b64encode(buf.getvalue()).decode()

        desc = ""
        try:
            desc = await asyncio.to_thread(vision.describe_screen)
        except Exception:
            pass

        return {
            "image_base64": img_b64,
            "description": desc,
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/vision/describe")
async def describe_image(image: UploadFile = File(...)):
    try:
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp.write(await image.read())
            tmp_path = tmp.name
        desc = await asyncio.to_thread(vision.describe_image, tmp_path)
        os.unlink(tmp_path)
        return {"description": desc}
    except Exception as e:
        raise HTTPException(500, str(e))


# ── Voice Transcription ──────────────────────────────────────────────
@app.post("/api/voice/transcribe")
async def transcribe_audio(audio: UploadFile = File(...)):
    """Accept WebM audio from the React UI and transcribe with Whisper."""
    try:
        with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as tmp:
            tmp.write(await audio.read())
            tmp_path = tmp.name

        text = await asyncio.to_thread(_stt_transcribe, tmp_path)
        os.unlink(tmp_path)
        return {"text": text, "language": "en"}
    except Exception as e:
        raise HTTPException(500, str(e))


def _stt_transcribe(audio_path: str) -> str:
    """Transcribe audio file using faster-whisper."""
    from faster_whisper import WhisperModel
    model = WhisperModel(
        config.WHISPER_MODEL_SIZE,
        device=config.WHISPER_DEVICE,
        compute_type=config.WHISPER_COMPUTE_TYPE
    )
    segments, _ = model.transcribe(audio_path, beam_size=5)
    return " ".join([s.text for s in segments]).strip()


# ── System Status ────────────────────────────────────────────────────
@app.get("/api/system/status")
async def system_status():
    import psutil
    gpu_pct = 0.0
    try:
        import subprocess
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used,memory.total",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            used, total = result.stdout.strip().split(", ")
            gpu_pct = round(float(used) / float(total) * 100, 1)
    except Exception:
        pass

    return {
        "cpu_percent": psutil.cpu_percent(),
        "ram_percent": psutil.virtual_memory().percent,
        "gpu_vram_percent": gpu_pct,
        "disk_percent": psutil.disk_usage("D:\\").percent,
        "jarvis_state": "idle",
        "uptime": f"{int(time.time() - START_TIME)}s",
        "session_count": len(conversations),
        "total_messages": sum(
            len(c["messages"]) for c in conversations.values()
        ),
    }


# ── Settings ─────────────────────────────────────────────────────────
@app.get("/api/settings")
async def get_settings():
    return _load_settings()


@app.post("/api/settings")
async def update_settings(req: SettingsUpdateRequest):
    settings = _load_settings()
    if req.primary_model:
        settings["primary_model"] = req.primary_model
    if req.voice_speed is not None:
        settings["voice_speed"] = req.voice_speed
    if req.theme:
        settings["theme"] = req.theme
    if req.wake_word_enabled is not None:
        settings["wake_word_enabled"] = req.wake_word_enabled
    _save_settings(settings)
    return {"updated": True, "settings": settings}


# ── API Key Endpoints ────────────────────────────────────────────────
@app.post("/api/keys/create")
async def create_api_key(req: APIKeyCreateRequest):
    result = key_mgr.create_key(req.name, req.permissions, req.rate_limit)
    return result


@app.get("/api/keys")
async def list_api_keys():
    return key_mgr.list_keys()


@app.delete("/api/keys/{key_id}")
async def revoke_api_key(key_id: str):
    ok = key_mgr.revoke_key(key_id)
    if not ok:
        raise HTTPException(404, "Key not found")
    return {"revoked": key_id}


@app.post("/api/keys/{key_id}/rotate")
async def rotate_api_key(key_id: str):
    result = key_mgr.rotate_key(key_id)
    if not result:
        raise HTTPException(404, "Key not found")
    return result


# ═══════════════════════════════════════════════════════════════════════
# WEBSOCKET ENDPOINT
# ═══════════════════════════════════════════════════════════════════════

@app.websocket("/ws/{session_id}")
async def websocket_endpoint(ws: WebSocket, session_id: str):
    await manager.connect(ws, session_id)
    _ensure_session(session_id)

    try:
        while True:
            data = await ws.receive_json()
            event_type = data.get("type")

            if event_type == "message":
                content = data.get("content", "")
                if not content:
                    continue

                # Append user message to SQLite
                session_db.add_message(session_id, "user", content)

                # Get memory context
                ctx = ""
                try:
                    ctx = await asyncio.to_thread(
                        memory.get_relevant_context, content
                    )
                except Exception:
                    pass

                # Stream response via WebSocket
                messages = _build_messages(session_id, content, ctx)

                async def ws_stream_callback(token: str):
                    await manager.send_token_to_session(session_id, token)

                # Temporarily swap the stream callback
                original_cb = llm.stream_callback
                llm.stream_callback = ws_stream_callback

                try:
                    response = await asyncio.to_thread(
                        llm.generate, messages, True  # stream=True
                    )
                except Exception as e:
                    response = f"Error: {e}"
                finally:
                    llm.stream_callback = original_cb

                await ws.send_json({
                    "type": "complete",
                    "content": response,
                })

                # Append JARVIS response to SQLite
                session_db.add_message(session_id, "jarvis", response)

                # Auto-title
                sess = session_db.get_session(session_id)
                if sess and len(sess.get("messages", [])) == 2:
                    try:
                        title = await asyncio.to_thread(
                            llm.generate,
                            [{"role": "user", "content":
                              f"Give this conversation a short 4-word title: {content}"}],
                            False, False, config.FAST_MODEL
                        )
                        clean_title = title.strip().strip('"').strip("'")[:50]
                        session_db.update_title(session_id, clean_title)
                        await ws.send_json({
                            "type": "title_update",
                            "title": clean_title,
                        })
                    except Exception:
                        pass

            elif event_type == "state_request":
                await ws.send_json({"type": "state", "state": "idle"})

            elif event_type == "ping":
                await ws.send_json({"type": "pong"})

    except WebSocketDisconnect:
        manager.disconnect(ws, session_id)


# ═══════════════════════════════════════════════════════════════════════
# STARTUP & RUN
# ═══════════════════════════════════════════════════════════════════════

@app.on_event("startup")
async def startup():
    global llm, tts, stt, intent, memory, vision, automation, email_h, code_e, image_gen, orchestrator, four_tier_memory

    logger.info("JARVIS API server starting...")

    # Initialize modules
    llm = IntelligentLLMEngine(
        config.JARVIS_SYSTEM_PROMPT,
        stream_callback=lambda t: asyncio.create_task(
            manager.broadcast_token(t)
        ),
        state_callback=lambda s: asyncio.create_task(
            manager.broadcast_state(s)
        ),
    )
    tts = StreamingTextToSpeech()
    stt = SpeechToText()
    intent = DualModelIntentClassifier(llm)
    memory = HybridRAGMemory(llm)
    four_tier_memory = FourTierMemorySystem(memory)
    vision = VisionEngine()
    automation = AutomationEngine()
    email_h = EmailHandler()
    code_e = CodeEngine()
    try:
        image_gen = ImageGenerationEngine()
    except Exception as e:
        logger.warning(f"Could not initialize ImageGenerationEngine: {e}")

    # Register tools into structured registry
    tool_registry.register("open_app", "Launch or open a desktop app", lambda app_name: automation.open_app(app_name))
    tool_registry.register("close_app", "Close an active desktop application", lambda app_name: automation.close_app(app_name))
    tool_registry.register("system_status", "Check system CPU, RAM, Disk, and metrics", lambda: automation.get_system_status())
    tool_registry.register("take_screenshot", "Capture screen image", lambda: automation.take_screenshot())
    tool_registry.register("describe_screen", "Analyze and describe what is visible on display", lambda: vision.describe_screen())
    tool_registry.register("search_memory", "Search past conversation memory and stored facts", lambda query: memory.get_relevant_context(query))
    tool_registry.register("execute_code", "Execute Python code in isolated sandbox", lambda code: code_e.execute_python(code), risk="high")
    tool_registry.register("list_windows", "List all open desktop application windows", lambda: computer_use.list_open_windows())
    tool_registry.register("focus_window", "Switch focus to a specific desktop application window", lambda window_name: computer_use.focus_window(window_name))
    tool_registry.register("browse_page", "Headlessly fetch clean page text without taking mouse focus", lambda url: asyncio.run(browser_agent.fetch_page_content(url)))

    # Mount dynamic skills
    skill_registry.discover_and_mount(tool_registry)

    # Initialize MCP Plugins if configured
    try:
        mcp_manager.start_all()
        # Register MCP tools into StructuredToolRegistry
        for mcp_tool in mcp_manager._all_tools:
            tool_registry.register(
                name=f"mcp__{mcp_tool.server_name}__{mcp_tool.name}",
                description=f"[MCP:{mcp_tool.server_name}] {mcp_tool.description}",
                func=lambda **kwargs: mcp_manager.clients[mcp_tool.server_name].call_tool(mcp_tool.name, kwargs),
                risk="medium"
            )
    except Exception as e:
        logger.warning(f"MCP Plugin auto-start: {e}")

    # Initialize Unified Orchestrator
    orchestrator = UnifiedAgentOrchestrator(
        llm=llm,
        tools=tool_registry,
        memory=memory,
        permission_engine=permission_engine
    )

    # Initialize Autonomous Workflow Engine
    workflow_engine = AutonomousWorkflowEngine(
        orchestrator=orchestrator,
        task_manager=task_manager
    )

    # Pre-warm models in background
    asyncio.create_task(asyncio.to_thread(llm.pre_warm))

    logger.info("JARVIS API ready on http://localhost:8080")


# Mount HUD static files
hud_dir = JARVIS_ROOT / "hud"
if hud_dir.exists():
    app.mount("/hud", StaticFiles(directory=str(hud_dir), html=True), name="hud")


if __name__ == "__main__":
    uvicorn.run(
        "api_server:app",
        host="0.0.0.0",
        port=8080,
        reload=False,
        log_level="info",
    )
