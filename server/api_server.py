"""
server/api_server.py — JARVIS FastAPI Backend (V2.1 Hardened)
=============================================================
Central nervous system for the JARVIS desktop application.
Uses JarvisRuntime container stored on `app.state.jarvis`.
Supports REST endpoints and WebSocket agent-step streaming.
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
from typing import Optional, List, Dict, Any

from fastapi import (
    FastAPI, WebSocket, WebSocketDisconnect, HTTPException,
    UploadFile, File, Form, Body, Header, Request, Depends
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import uvicorn

# ── Add JARVIS root to path ────────────────────────────────────────────
JARVIS_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(JARVIS_ROOT))

import config
from server.runtime import JarvisRuntime
from modules.security.permission_engine import ActionCategory

logger = logging.getLogger(__name__)

# ── Local Token & Authentication Setup ────────────────────────────────
TOKEN_FILE = config.DATA_DIR / ".jarvis_local_token"

def _get_or_create_local_token() -> str:
    """Generates or retrieves persistent local authentication token for loopback API."""
    if TOKEN_FILE.exists():
        try:
            tok = TOKEN_FILE.read_text(encoding="utf-8").strip()
            if tok:
                return tok
        except Exception:
            pass
    new_token = f"jarvis_{uuid.uuid4().hex}"
    try:
        TOKEN_FILE.write_text(new_token, encoding="utf-8")
    except Exception as e:
        logger.warning(f"Could not persist local token: {e}")
    return new_token

LOCAL_AUTH_TOKEN = _get_or_create_local_token()

# ── App Setup ──────────────────────────────────────────────────────────
app = FastAPI(
    title="JARVIS API",
    version="3.1",
    description="JARVIS Local AI Backend — Zero Cloud Dependencies"
)

# CORS Lockdown: restrict strictly to local desktop and frontend origins
ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:8080",
    "http://127.0.0.1:8080",
    "electron://*",
    "file://*",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["*"],
)

START_TIME = time.time()
SETTINGS_FILE = config.DATA_DIR / "user_settings.json"


# ── Dependency: Runtime Accessor ──────────────────────────────────────
def get_runtime(request: Request) -> JarvisRuntime:
    return request.app.state.jarvis


# ── Authentication Middleware ─────────────────────────────────────────
@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    """Enforces mandatory authentication on all /api/ endpoints except health."""
    path = request.url.path
    if request.method == "OPTIONS" or path in ("/health", "/api/health", "/"):
        return await call_next(request)

    if path.startswith("/api/"):
        auth_header = request.headers.get("Authorization") or ""
        token = ""
        if auth_header.startswith("Bearer "):
            token = auth_header[7:].strip()
        elif "x-api-key" in request.headers:
            token = request.headers["x-api-key"].strip()

        if not token or token != LOCAL_AUTH_TOKEN:
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=401,
                content={"detail": "Unauthorized: Valid local authentication token required."},
                headers={"WWW-Authenticate": "Bearer"}
            )

    return await call_next(request)


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
    session_id: Optional[str] = None

class ImageEditRequest(BaseModel):
    init_image: str  # base64 data url or raw base64
    prompt: str
    mask_image: Optional[str] = None
    negative_prompt: Optional[str] = ""
    model: Optional[str] = "auto"
    denoising_strength: Optional[float] = 0.65
    steps: Optional[int] = 20
    cfg_scale: Optional[float] = 7.0
    session_id: Optional[str] = None
    parent_asset_id: Optional[int] = None
    reference_images: Optional[List[str]] = None

class VisualSessionCreateRequest(BaseModel):
    session_id: Optional[str] = None
    title: Optional[str] = "New Visual Session"
    mode: Optional[str] = "generate"

class AutonomousGoalRequest(BaseModel):
    goal: str
    title: Optional[str] = None

class ProceduralPreferenceRequest(BaseModel):
    key: str
    category: str
    preference: str

class ApprovalDecisionRequest(BaseModel):
    request_id: str
    approved: bool


# ── Settings Helpers ──────────────────────────────────────────────────
def _load_settings() -> dict:
    if SETTINGS_FILE.exists():
        try:
            return json.loads(SETTINGS_FILE.read_text())
        except Exception:
            pass
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


def _build_messages(session_db, session_id: str, user_content: str,
                    memory_context: str = "") -> list:
    """Build message list for LLM fallback from persistent conversation history."""
    msgs = [{"role": "system", "content": config.JARVIS_SYSTEM_PROMPT}]

    if memory_context:
        msgs.append({
            "role": "system",
            "content": f"Relevant memory context:\n{memory_context}"
        })

    sess = session_db.get_session(session_id)
    if sess and sess.get("messages"):
        for m in sess["messages"][-config.MAX_HISTORY_TURNS * 2:]:
            role = "user" if m["role"] == "user" else "assistant"
            msgs.append({"role": role, "content": m["content"]})

    msgs.append({"role": "user", "content": user_content})
    return msgs


# ═══════════════════════════════════════════════════════════════════════
# REST ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════

# ── Health ─────────────────────────────────────────────────────────────
@app.get("/health")
@app.get("/api/health")
async def health(request: Request):
    ollama_ok = False
    try:
        import ollama as _ollama
        _ollama.list()
        ollama_ok = True
    except Exception:
        pass
    return {
        "status": "ok",
        "version": "3.0.6",
        "ollama": ollama_ok,
        "uptime_seconds": int(time.time() - START_TIME),
        "auth_required": True
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
async def create_session(req: NewSessionRequest, rt: JarvisRuntime = Depends(get_runtime)):
    sid = str(uuid.uuid4())
    return rt.session_db.create_session(sid, req.title or "New conversation")


@app.get("/api/sessions")
async def list_sessions(rt: JarvisRuntime = Depends(get_runtime)):
    return rt.session_db.list_sessions()


@app.get("/api/sessions/{session_id}")
async def get_session(session_id: str, rt: JarvisRuntime = Depends(get_runtime)):
    sess = rt.session_db.get_session(session_id)
    if not sess:
        raise HTTPException(404, "Session not found")
    return sess


@app.delete("/api/sessions/{session_id}")
async def delete_session(session_id: str, rt: JarvisRuntime = Depends(get_runtime)):
    rt.session_db.delete_session(session_id)
    return {"deleted": session_id}


# ── Autonomous Workflow Endpoints ────────────────────────────────────
@app.post("/api/workflows/goal")
async def start_autonomous_goal(req: AutonomousGoalRequest, rt: JarvisRuntime = Depends(get_runtime)):
    if not rt.workflow_engine:
        raise HTTPException(500, "Autonomous Workflow Engine not ready.")
    task_id = await rt.workflow_engine.start_autonomous_goal(req.goal, req.title)
    return {"task_id": task_id, "status": "QUEUED", "goal": req.goal}


# ── Computer Use & Telemetry Endpoints ───────────────────────────────
@app.get("/api/windows/active")
async def get_active_window(rt: JarvisRuntime = Depends(get_runtime)):
    return rt.computer_use.get_active_window()


@app.get("/api/windows/list")
async def list_open_windows(rt: JarvisRuntime = Depends(get_runtime)):
    return {"windows": rt.computer_use.list_open_windows()}


@app.post("/api/windows/focus")
async def focus_window(query: str, rt: JarvisRuntime = Depends(get_runtime)):
    ok = rt.computer_use.focus_window(query)
    return {"success": ok}


@app.get("/api/gpu/telemetry")
async def get_gpu_telemetry(rt: JarvisRuntime = Depends(get_runtime)):
    return rt.gpu_scheduler.get_gpu_telemetry()


# ── Skills & MCP Endpoints ───────────────────────────────────────────
@app.get("/api/skills")
async def list_skills(rt: JarvisRuntime = Depends(get_runtime)):
    return {"skills": rt.skill_registry.list_loaded_skills()}


@app.get("/api/mcp/servers")
async def list_mcp_servers(rt: JarvisRuntime = Depends(get_runtime)):
    return {
        "servers": list(rt.mcp_manager.clients.keys()),
        "tools": [t.to_llm_schema() for t in rt.mcp_manager._all_tools]
    }


# ── Background Tasks Endpoints ───────────────────────────────────────
@app.get("/api/tasks")
async def list_tasks(rt: JarvisRuntime = Depends(get_runtime)):
    return {"tasks": rt.task_manager.list_tasks()}


@app.get("/api/tasks/{task_id}")
async def get_task(task_id: str, rt: JarvisRuntime = Depends(get_runtime)):
    t = rt.task_manager.get_task(task_id)
    if not t:
        raise HTTPException(404, "Task not found")
    return t


@app.post("/api/tasks/{task_id}/cancel")
async def cancel_task(task_id: str, rt: JarvisRuntime = Depends(get_runtime)):
    rt.task_manager.cancel_task(task_id)
    return {"cancelled": task_id}


@app.post("/api/tasks/{task_id}/resume")
async def resume_task(task_id: str, rt: JarvisRuntime = Depends(get_runtime)):
    success = await rt.workflow_engine.resume_goal(task_id)
    if not success:
        raise HTTPException(404, f"Task {task_id} could not be resumed")
    return {"resumed": task_id}


# ── Interactive Security Approval Endpoint ───────────────────────────
@app.post("/api/security/approve")
async def submit_approval_decision(req: ApprovalDecisionRequest, rt: JarvisRuntime = Depends(get_runtime)):
    """Resolves pending user approval requests generated by high-risk actions."""
    resolved = rt.permission_engine.resolve_approval_request(req.request_id, req.approved)
    if not resolved:
        raise HTTPException(404, "Approval request ID not found or already resolved.")
    return {"request_id": req.request_id, "approved": req.approved, "status": "resolved"}


# ── Chat (Main Endpoint) ─────────────────────────────────────────────
@app.post("/api/message")
async def send_message(req: MessageRequest, rt: JarvisRuntime = Depends(get_runtime)):
    start_t = time.time()
    sid = req.session_id
    rt.session_db.create_session(sid)

    # 1. Append user message to SQLite
    rt.session_db.add_message(sid, "user", req.content)

    # 2. Classify intent
    classified = await asyncio.to_thread(rt.intent.classify, req.content)
    intent_name = classified.get("intent", "chat")

    # 3. Check Security / Permission Gate for classified high-risk actions
    if intent_name in (ActionCategory.SEND_EMAIL, ActionCategory.SEND_WHATSAPP, ActionCategory.DELETE_FILE, ActionCategory.SYSTEM_SHUTDOWN):
        authorized, reason = await rt.permission_engine.verify_and_authorize(intent_name, {"query": req.content}, session_id=sid)
        if not authorized:
            refusal_response = f"I require your explicit authorization to proceed with {intent_name.replace('_', ' ')}, sir. Action was not executed."
            rt.session_db.add_message(sid, "jarvis", refusal_response)
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
        ctx = await asyncio.to_thread(rt.memory.get_relevant_context, req.content)
    except Exception as e:
        logger.warning(f"Memory retrieval failed: {e}")

    # 5. Generate response via Unified Agent Orchestrator
    response_text = ""
    try:
        sess = rt.session_db.get_session(sid)
        history = sess.get("messages", [])[:-1] if sess else []

        if rt.orchestrator:
            async def _forward_agent_step(event):
                if isinstance(event, dict):
                    await rt.manager.send_to_session(sid, event)
                else:
                    await rt.manager.send_to_session(sid, {"type": "agent_step", "step": str(event)})

            response_text = await rt.orchestrator.execute_task(
                query=req.content,
                conversation_history=history,
                session_id=sid,
                step_callback=_forward_agent_step
            )
        else:
            messages = _build_messages(rt.session_db, sid, req.content, ctx)
            response_text = await asyncio.to_thread(
                rt.llm.generate, messages, False
            )
    except Exception as e:
        logger.error(f"Orchestrator generation failed: {e}", exc_info=True)
        response_text = "I'm experiencing a temporary issue with my reasoning engine, sir. Please try again."

    # 6. Append JARVIS response to SQLite
    rt.session_db.add_message(sid, "jarvis", response_text)

    # 7. Auto-title first message
    sess = rt.session_db.get_session(sid)
    if sess and len(sess.get("messages", [])) == 2:
        try:
            title = await asyncio.to_thread(
                rt.llm.generate,
                [{"role": "user", "content":
                  f"Give this conversation a short 4-word title: {req.content}"}],
                False, False, config.FAST_MODEL
            )
            clean_title = title.strip().strip('"').strip("'")[:50]
            rt.session_db.update_title(sid, clean_title)
        except Exception:
            pass

    # 8. Extract facts in background
    try:
        asyncio.get_event_loop().run_in_executor(
            None, rt.memory.extract_and_store_facts, req.content, response_text
        )
    except Exception:
        pass

    # 9. TTS if requested
    if req.use_voice and rt.tts:
        try:
            asyncio.get_event_loop().run_in_executor(
                None, rt.tts.speak, response_text
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
async def quick_command(req: CommandRequest, rt: JarvisRuntime = Depends(get_runtime)):
    classified = await asyncio.to_thread(rt.intent.classify, req.command)
    messages = _build_messages(rt.session_db, req.session_id, req.command)
    response = await asyncio.to_thread(rt.llm.generate, messages, False)
    return {
        "response": response,
        "intent": classified.get("intent", "chat"),
    }


# ── Memory Endpoints ─────────────────────────────────────────────────
@app.get("/api/memory/facts")
async def get_facts(rt: JarvisRuntime = Depends(get_runtime)):
    try:
        results = rt.memory.facts_col.get(include=["documents", "metadatas"])
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
async def search_memory(q: str, rt: JarvisRuntime = Depends(get_runtime)):
    try:
        results = await asyncio.to_thread(rt.memory.get_relevant_context, q)
        return {"results": [{"text": results, "score": 1.0, "source": "hybrid"}]}
    except Exception as e:
        return {"results": [], "error": str(e)}


@app.post("/api/memory/add")
async def add_memory(req: MemoryAddRequest, rt: JarvisRuntime = Depends(get_runtime)):
    try:
        await asyncio.to_thread(
            rt.memory.add_fact, req.fact,
            {"category": req.category, "timestamp": datetime.now().isoformat()}
        )
        return {"added": req.fact}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.delete("/api/memory/{fact_id}")
async def delete_memory(fact_id: str, rt: JarvisRuntime = Depends(get_runtime)):
    try:
        deleted = rt.memory.delete_fact(fact_id)
        return {"deleted": fact_id, "success": deleted}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/memory/clear")
async def clear_memory(x_confirm: Optional[str] = Header(None), rt: JarvisRuntime = Depends(get_runtime)):
    if x_confirm != "CLEAR_ALL_MEMORY":
        raise HTTPException(403, "Missing confirmation header: X-Confirm: CLEAR_ALL_MEMORY")
    try:
        rt.memory.clear_all()
        return {"cleared": True}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/memory/status")
async def get_memory_extraction_status(rt: JarvisRuntime = Depends(get_runtime)):
    if not rt.memory:
        return {"status": "uninitialized"}
    queue_size = getattr(rt.memory, "_task_queue", None)
    q_len = queue_size.qsize() if queue_size else 0
    last_status = getattr(rt.memory, "last_extraction_status", {"status": "idle"})
    return {
        "queue_length": q_len,
        "last_status": last_status
    }


# ── 4-Tier Memory Endpoints ───────────────────────────────────────────
@app.get("/api/memory/working")
async def get_working_memory(session_id: Optional[str] = None, rt: JarvisRuntime = Depends(get_runtime)):
    if not rt.four_tier_memory:
        return {"session_id": session_id or "default", "active_rules": [], "recent_goals": []}
    return rt.four_tier_memory.get_working_memory_state(session_id=session_id)


@app.get("/api/memory/episodic")
async def get_episodic_memory(limit: int = 15, rt: JarvisRuntime = Depends(get_runtime)):
    if not rt.four_tier_memory:
        return {"episodes": []}
    episodes = rt.four_tier_memory.get_recent_episodes(limit=limit)
    return {"episodes": episodes}


@app.delete("/api/memory/episodic/{episode_id}")
async def delete_episodic_memory(episode_id: int, rt: JarvisRuntime = Depends(get_runtime)):
    if not rt.four_tier_memory:
        raise HTTPException(500, "Four-tier memory not active")
    deleted = rt.four_tier_memory.delete_episode(episode_id)
    if not deleted:
        raise HTTPException(404, f"Episode {episode_id} not found")
    return {"deleted": episode_id}


@app.get("/api/memory/procedural")
async def get_procedural_memory(rt: JarvisRuntime = Depends(get_runtime)):
    if not rt.four_tier_memory:
        return {"preferences": []}
    prefs = rt.four_tier_memory.get_all_procedural_preferences()
    return {"preferences": prefs}


@app.post("/api/memory/procedural")
async def add_procedural_memory(req: ProceduralPreferenceRequest, rt: JarvisRuntime = Depends(get_runtime)):
    if not rt.four_tier_memory:
        raise HTTPException(500, "Four-tier memory not active")
    rt.four_tier_memory.set_procedural_preference(key=req.key, category=req.category, preference=req.preference)
    return {"status": "saved", "key": req.key, "preference": req.preference}


@app.delete("/api/memory/procedural/{key}")
async def delete_procedural_memory(key: str, rt: JarvisRuntime = Depends(get_runtime)):
    if not rt.four_tier_memory:
        raise HTTPException(500, "Four-tier memory not active")
    deleted = rt.four_tier_memory.delete_procedural_preference(key)
    if not deleted:
        raise HTTPException(404, f"Procedural key '{key}' not found")
    return {"deleted": key}


# ── Image Generation Endpoints ───────────────────────────────────────
@app.get("/api/image/models")
async def list_image_models(mode: Optional[str] = None):
    """
    List 100% locally hosted image models from SD WebUI Forge.
    Filters models by target mode:
      - mode='generate': returns standard generative checkpoints (DreamShaper, Realistic Vision)
      - mode='edit': returns dedicated inpainting and editing models (Realistic Vision Inpainting, ControlNet IP2P, etc.)
      - mode=None / omitted: returns all models
    """
    models = []
    local_models_found = []

    # 1. Query running Forge instance for loaded checkpoints
    try:
        import requests
        forge_url = getattr(config, "SD_LOCAL_URL", "http://127.0.0.1:7860")
        resp = requests.get(f"{forge_url}/sdapi/v1/sd-models", timeout=1.5)
        if resp.status_code == 200:
            for item in resp.json():
                title = item.get("title") or item.get("model_name") or "Local Model"
                local_models_found.append(title)
                title_lower = title.lower()

                # Determine architecture family & capabilities
                is_inpaint = "inpaint" in title_lower or "inpainting" in title_lower or "ip2p" in title_lower
                if "flux" in title_lower:
                    category = "FLUX"
                    desc = f"Local FLUX model (4-step Schnell / NF4 high fidelity): {item.get('filename', title)}"
                    default_steps = 4
                    default_cfg = 1.0
                    default_dim = 1024
                elif "xl" in title_lower or "sdxl" in title_lower:
                    category = "SDXL"
                    desc = f"Local SDXL model: {item.get('filename', title)}"
                    default_steps = 25
                    default_cfg = 6.0
                    default_dim = 1024
                elif is_inpaint:
                    category = "Inpainting"
                    desc = f"Dedicated Local Inpaint Engine (Preserves identity & unmasked regions): {item.get('filename', title)}"
                    default_steps = 25
                    default_cfg = 7.0
                    default_dim = 512
                else:
                    category = "SD1.5"
                    desc = f"Local SD 1.5 checkpoint: {item.get('filename', title)}"
                    default_steps = 20
                    default_cfg = 7.0
                    default_dim = 512

                models.append({
                    "id": f"local:{title}",
                    "name": title,
                    "source": "forge",
                    "category": category,
                    "is_edit_model": is_inpaint,
                    "description": desc,
                    "default_steps": default_steps,
                    "default_cfg": default_cfg,
                    "default_dim": default_dim,
                })
    except Exception:
        pass

    # 2. Check disk directly if Forge is still booting up or refreshing
    models_dir = Path(config.BASE_DIR) / "tools" / "forge" / "webui" / "models" / "Stable-diffusion"
    if models_dir.exists():
        for f in models_dir.glob("*.safetensors"):
            title = f.stem
            if any(m["name"] == title or m["id"] == f"local:{title}" for m in models):
                continue
            title_lower = title.lower()
            is_inpaint = "inpaint" in title_lower or "inpainting" in title_lower or "ip2p" in title_lower
            if "flux" in title_lower:
                category = "FLUX"
                capabilities = ["text_to_image"]
                vram_estimate = 6144
            elif "xl" in title_lower or "sdxl" in title_lower:
                category = "SDXL"
                capabilities = ["text_to_image", "image_to_image"]
                vram_estimate = 5120
            elif is_inpaint:
                category = "Inpainting"
                capabilities = ["inpainting", "image_to_image"]
                vram_estimate = 3584
            else:
                category = "SD1.5"
                capabilities = ["text_to_image", "image_to_image"]
                vram_estimate = 3584

            models.append({
                "id": f"local:{title}",
                "name": title,
                "source": "forge",
                "category": category,
                "capabilities": capabilities,
                "vram_estimate_mb": vram_estimate,
                "is_edit_model": is_inpaint,
                "description": f"Dedicated Inpaint Model" if is_inpaint else f"Local GPU Checkpoint ({category}) on disk",
                "default_steps": 4 if category == "FLUX" else 20,
                "default_cfg": 1.0 if category == "FLUX" else 7.0,
                "default_dim": 1024 if category in ("FLUX", "SDXL") else 512,
            })

    # 3. Check ControlNet models directory for edit models
    cn_dir = Path(config.BASE_DIR) / "tools" / "forge" / "webui" / "models" / "ControlNet"
    if cn_dir.exists():
        for f in cn_dir.glob("*.safetensors"):
            title = f.stem
            title_lower = title.lower()
            if "ip2p" in title_lower:
                name_display = "InstructPix2Pix (Instruction Edit)"
                capabilities = ["instruction_edit", "image_to_image"]
            elif "inpaint" in title_lower:
                name_display = "ControlNet Inpaint FP16 (Pixel Lock)"
                capabilities = ["inpainting", "pixel_lock"]
            elif "openpose" in title_lower:
                name_display = "ControlNet OpenPose (Pose Lock)"
                capabilities = ["pose_lock"]
            else:
                name_display = f"ControlNet {title}"
                capabilities = ["controlnet_guided"]

            models.append({
                "id": f"controlnet:{title}",
                "name": name_display,
                "source": "controlnet",
                "category": "ControlNet",
                "capabilities": capabilities,
                "vram_estimate_mb": 4096,
                "is_edit_model": True,
                "description": "Guided instruction & feature-preserving edit engine",
                "default_steps": 20,
                "default_cfg": 7.5,
                "default_dim": 512,
            })

    # 4. Fallback if empty
    if not models:
        models.append({
            "id": "local:DreamShaper_8_pruned",
            "name": "DreamShaper 8 (Local SD 1.5)",
            "source": "forge",
            "category": "SD1.5",
            "is_edit_model": False,
            "description": "Local SD Forge running DreamShaper 8 on NVIDIA RTX GPU",
            "default_steps": 20,
            "default_cfg": 7.0,
            "default_dim": 512,
        })

    # Filter based on requested mode:
    if mode == "generate":
        filtered = [m for m in models if not m.get("is_edit_model", False)]
        return {"models": filtered if filtered else models}
    elif mode == "edit":
        filtered = [m for m in models if m.get("is_edit_model", False)]
        # If no edit-specific models downloaded yet, allow base checkpoints as fallback
        return {"models": filtered if filtered else models}

    return {"models": models}


@app.post("/api/image/generate")
async def generate_image_api(req: ImageGenRequest, rt: JarvisRuntime = Depends(get_runtime)):
    if not rt.image_gen:
        raise HTTPException(500, "Image generation engine not initialized.")

    working_prompt = req.prompt
    enhanced_prompt = req.prompt
    if req.enhance_prompt and rt.llm:
        try:
            enhanced_prompt = await asyncio.to_thread(rt.image_gen.enhance_prompt, req.prompt, rt.llm)
            working_prompt = enhanced_prompt
        except Exception:
            working_prompt = req.prompt

    model_choice = req.model or "local"

    # GPU VRAM Coordination: park Ollama models before local SD Forge generation
    try:
        await rt.gpu_scheduler.prepare_for_image_gen()
    except Exception as e:
        logger.warning(f"GPU scheduler park failed: {e}")

    # Extract specific checkpoint title if present
    checkpoint_title = None
    if model_choice.startswith("local:"):
        checkpoint_title = model_choice[len("local:"):]

    is_flux = (checkpoint_title and "flux" in checkpoint_title.lower()) or "flux" in model_choice.lower()
    steps = req.steps or (4 if is_flux else 20)
    cfg = 1.0 if is_flux else 7.0
    width = req.width or (1024 if is_flux else 512)
    height = req.height or (1024 if is_flux else 512)

    img_bytes = await asyncio.to_thread(
        rt.image_gen._generate_local,
        working_prompt,
        req.negative_prompt or "",
        steps,
        width,
        height,
        cfg,
        "Euler" if is_flux else "Euler a",
        checkpoint_title
    )

    if not img_bytes:
        raise HTTPException(
            503,
            "Local Stable Diffusion Forge engine is currently offline or loading. "
            "Please ensure Forge is running on port 7860."
        )

    source = f"Local GPU ({checkpoint_title or 'DreamShaper 8'})"

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    filename = f"gen_{timestamp}.png"
    filepath = rt.image_gen.save_dir / filename
    try:
        with open(filepath, "wb") as f:
            f.write(img_bytes)
    except Exception as e:
        logger.warning(f"Failed to save generated image to disk: {e}")

    img_b64 = base64.b64encode(img_bytes).decode("utf-8")

    # Index into visual assets database if active
    asset_id = None
    if rt.image_studio_db:
        try:
            asset = rt.image_studio_db.add_asset(
                asset_type="generated",
                filepath=str(filepath),
                session_id=req.session_id,
                prompt=req.prompt,
                negative_prompt=req.negative_prompt or "",
                model=model_choice,
                width=width,
                height=height,
                aspect_ratio=f"{width}:{height}"
            )
            asset_id = asset.get("id")
        except Exception as e:
            logger.warning(f"Failed to record generated image in studio db: {e}")

    return {
        "id": asset_id,
        "image_base64": img_b64,
        "source": source,
        "filepath": str(filepath),
        "prompt": req.prompt,
        "enhanced_prompt": enhanced_prompt
    }


# ── Image Studio Pro Endpoints (Upload, Edit, Sessions, Library) ───────
from fastapi import UploadFile, File, Form

@app.post("/api/image/upload")
async def upload_image_api(
    file: UploadFile = File(...),
    session_id: Optional[str] = Form(None),
    rt: JarvisRuntime = Depends(get_runtime)
):
    if not rt.image_edit or not rt.image_studio_db:
        raise HTTPException(500, "Image Studio engine not initialized.")

    contents = await file.read()
    if not contents:
        raise HTTPException(400, "Empty upload payload.")

    try:
        filepath, b64_str, width, height = await asyncio.to_thread(
            rt.image_edit.save_uploaded_image, contents, file.filename or "upload.png"
        )
        asset = rt.image_studio_db.add_asset(
            asset_type="uploaded",
            filepath=filepath,
            session_id=session_id,
            prompt=file.filename or "Uploaded Image",
            width=width,
            height=height
        )
        return {
            "id": asset["id"],
            "image_base64": b64_str,
            "filepath": filepath,
            "width": width,
            "height": height,
            "asset_type": "uploaded"
        }
    except Exception as e:
        logger.error(f"Image upload failed: {e}", exc_info=True)
        raise HTTPException(500, f"Image upload failed: {str(e)}")


@app.post("/api/image/edit")
async def edit_image_api(req: ImageEditRequest, rt: JarvisRuntime = Depends(get_runtime)):
    if not rt.image_edit or not rt.image_studio_db:
        raise HTTPException(500, "Image Edit engine not initialized.")

    if not req.init_image or not req.prompt:
        raise HTTPException(400, "Both init_image and edit prompt are required.")

    # GPU VRAM Coordination: park Ollama before local SD Forge img2img
    try:
        await rt.gpu_scheduler.prepare_for_image_gen()
    except Exception as e:
        logger.warning(f"GPU scheduler park failed: {e}")

    # Forward model spec (whether local: or controlnet:) directly to edit engine
    model_choice = req.model or "local"

    edited_bytes = await asyncio.to_thread(
        rt.image_edit.edit_image,
        req.init_image,
        req.prompt,
        req.mask_image,
        req.negative_prompt or "",
        req.denoising_strength or 0.65,
        req.steps or 20,
        req.cfg_scale or 7.0,
        "Euler a",
        model_choice,
        req.reference_images
    )

    if not edited_bytes:
        raise HTTPException(
            503,
            "Local Stable Diffusion Forge engine failed to edit the image or is offline on port 7860."
        )

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    filename = f"edit_{timestamp}.png"
    filepath = rt.image_edit.save_dir / filename
    try:
        with open(filepath, "wb") as f:
            f.write(edited_bytes)
    except Exception as e:
        logger.warning(f"Failed to save edited image: {e}")

    b64_str = base64.b64encode(edited_bytes).decode("utf-8")

    asset = rt.image_studio_db.add_asset(
        asset_type="edited",
        filepath=str(filepath),
        session_id=req.session_id,
        prompt=req.prompt,
        negative_prompt=req.negative_prompt or "",
        model=req.model or "local",
        parent_asset_id=req.parent_asset_id
    )

    return {
        "id": asset["id"],
        "image_base64": b64_str,
        "filepath": str(filepath),
        "prompt": req.prompt,
        "source": "Local SD Forge (img2img/inpaint)",
        "parent_asset_id": req.parent_asset_id
    }


@app.get("/api/image/sessions")
async def list_visual_sessions(limit: int = 50, rt: JarvisRuntime = Depends(get_runtime)):
    if not rt.image_studio_db:
        return {"sessions": []}
    return {"sessions": rt.image_studio_db.list_sessions(limit=limit)}


@app.post("/api/image/sessions/new")
async def create_visual_session(req: VisualSessionCreateRequest, rt: JarvisRuntime = Depends(get_runtime)):
    if not rt.image_studio_db:
        raise HTTPException(500, "Studio DB not active")
    import uuid
    sid = req.session_id or f"vis_{uuid.uuid4().hex[:12]}"
    sess = rt.image_studio_db.create_session(sid, req.title or "New Visual Session", req.mode or "generate")
    return sess


@app.get("/api/image/sessions/{session_id}")
async def get_visual_session(session_id: str, rt: JarvisRuntime = Depends(get_runtime)):
    if not rt.image_studio_db:
        raise HTTPException(500, "Studio DB not active")
    sess = rt.image_studio_db.get_session(session_id)
    if not sess:
        raise HTTPException(404, "Visual session not found")
    
    # Read files to base64 if needed for active canvas rendering
    for asset in sess.get("assets", []):
        fp = asset.get("filepath")
        is_video = asset.get("asset_type") == "video" or (fp and fp.endswith(".mp4"))
        # Do NOT load full video files as base64 into the session JSON payload to protect RAM
        if is_video:
            continue
        if fp and os.path.exists(fp):
            try:
                with open(fp, "rb") as f:
                    asset["image_base64"] = base64.b64encode(f.read()).decode("utf-8")
            except Exception:
                pass
    return sess


@app.delete("/api/image/sessions/{session_id}")
async def delete_visual_session(session_id: str, rt: JarvisRuntime = Depends(get_runtime)):
    if not rt.image_studio_db:
        raise HTTPException(500, "Studio DB not active")
    rt.image_studio_db.delete_session(session_id)
    return {"status": "deleted", "session_id": session_id}


@app.patch("/api/image/sessions/{session_id}/state")
async def update_session_state(
    session_id: str,
    payload: Dict[str, Any] = Body(...),
    rt: JarvisRuntime = Depends(get_runtime)
):
    if not rt.image_studio_db:
        raise HTTPException(500, "Studio DB not active")
    success = rt.image_studio_db.update_session_workspace_state(session_id, payload)
    return {"status": "updated" if success else "failed", "session_id": session_id}


@app.post("/api/image/upscale")
async def upscale_image_api(
    payload: Dict[str, Any] = Body(...),
    rt: JarvisRuntime = Depends(get_runtime)
):
    if not rt.image_edit or not rt.image_studio_db:
        raise HTTPException(500, "Image Studio engine not initialized.")

    image_b64 = payload.get("image")
    if not image_b64:
        raise HTTPException(400, "No image provided for upscaling.")

    upscaler_name = payload.get("upscaler", "R-ESRGAN 4x+")
    scale = float(payload.get("scale", 2.0))
    session_id = payload.get("session_id")
    parent_asset_id = payload.get("parent_asset_id")

    # Park Ollama to free VRAM for hardware upscaler
    try:
        await rt.gpu_scheduler.prepare_for_image_gen()
    except Exception as e:
        logger.warning(f"GPU scheduler park failed: {e}")

    upscaled_bytes = await asyncio.to_thread(
        rt.image_edit.upscale_image,
        image_b64,
        upscaler_name,
        scale
    )

    if not upscaled_bytes:
        raise HTTPException(503, "Local hardware upscaling failed or SD Forge is offline.")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    filename = f"upscale_{timestamp}.png"
    filepath = rt.image_edit.save_dir / filename
    try:
        with open(filepath, "wb") as f:
            f.write(upscaled_bytes)
    except Exception as e:
        logger.warning(f"Failed to save upscaled image: {e}")

    b64_str = base64.b64encode(upscaled_bytes).decode("utf-8")

    asset = rt.image_studio_db.add_asset(
        asset_type="edited",
        filepath=str(filepath),
        session_id=session_id,
        prompt=f"Upscaled {scale}x ({upscaler_name})",
        model=f"upscale:{upscaler_name}",
        parent_asset_id=parent_asset_id
    )

    return {
        "id": asset["id"],
        "image_base64": b64_str,
        "filepath": str(filepath),
        "source": f"Local Forge ({upscaler_name})",
        "parent_asset_id": parent_asset_id
    }


@app.post("/api/image/segment")
async def segment_image_api(
    payload: Dict[str, Any] = Body(...),
    rt: JarvisRuntime = Depends(get_runtime)
):
    if not rt.image_edit:
        raise HTTPException(500, "Image Studio engine not initialized.")

    image_b64 = payload.get("image")
    if not image_b64:
        raise HTTPException(400, "No image provided for segmentation.")

    module = payload.get("module", "seg_ofade20k")
    resolution = int(payload.get("resolution", 512))

    # Park Ollama to free VRAM for segmentation preprocessor
    try:
        await rt.gpu_scheduler.prepare_for_image_gen()
    except Exception as e:
        logger.warning(f"GPU scheduler park failed: {e}")

    mask_bytes = await asyncio.to_thread(
        rt.image_edit.segment_image,
        image_b64,
        module,
        resolution
    )

    if not mask_bytes:
        raise HTTPException(503, "Neural segmentation failed or SD Forge is offline.")

    b64_str = base64.b64encode(mask_bytes).decode("utf-8")
    return {
        "mask_base64": b64_str,
        "module": module
    }


@app.post("/api/image/remove-bg")
async def remove_background_api(
    payload: Dict[str, Any] = Body(...),
    rt: JarvisRuntime = Depends(get_runtime)
):
    if not rt.image_edit or not rt.image_studio_db:
        raise HTTPException(500, "Image Studio engine not initialized.")

    image_b64 = payload.get("image")
    if not image_b64:
        raise HTTPException(400, "No image provided for background removal.")

    session_id = payload.get("session_id")
    parent_asset_id = payload.get("parent_asset_id")

    rgba_bytes = await asyncio.to_thread(
        rt.image_edit.remove_background,
        image_b64
    )

    if not rgba_bytes:
        raise HTTPException(500, "Background removal processing failed.")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    filename = f"rembg_{timestamp}.png"
    filepath = rt.image_edit.save_dir / filename
    try:
        with open(filepath, "wb") as f:
            f.write(rgba_bytes)
    except Exception as e:
        logger.warning(f"Failed to save transparent PNG: {e}")

    b64_str = base64.b64encode(rgba_bytes).decode("utf-8")

    asset = rt.image_studio_db.add_asset(
        asset_type="edited",
        filepath=str(filepath),
        session_id=session_id,
        prompt="Isolated Subject (Transparent Background)",
        model="tool:remove_background",
        parent_asset_id=parent_asset_id
    )

    return {
        "id": asset["id"],
        "image_base64": b64_str,
        "filepath": str(filepath),
        "source": "Local Background Removal",
        "parent_asset_id": parent_asset_id
    }


@app.post("/api/image/replace-bg")
async def replace_background_api(
    payload: Dict[str, Any] = Body(...),
    rt: JarvisRuntime = Depends(get_runtime)
):
    if not rt.image_edit or not rt.image_studio_db:
        raise HTTPException(500, "Image Studio engine not initialized.")

    image_b64 = payload.get("image")
    prompt = payload.get("prompt")
    if not image_b64 or not prompt:
        raise HTTPException(400, "Both 'image' and 'prompt' are required for background replacement.")

    session_id = payload.get("session_id")
    parent_asset_id = payload.get("parent_asset_id")
    negative_prompt = payload.get("negative_prompt", "")
    denoising_strength = float(payload.get("denoising_strength", 0.85))
    steps = int(payload.get("steps", 25))
    cfg_scale = float(payload.get("cfg_scale", 7.0))

    try:
        from core.system_monitor import system_monitor
        system_monitor.park_for_media_generation()
    except Exception as e:
        logger.warning(f"Failed to park system monitor/Ollama for replace-bg: {e}")

    result_bytes = await asyncio.to_thread(
        rt.image_edit.replace_background,
        image_b64,
        prompt,
        negative_prompt,
        denoising_strength,
        steps,
        cfg_scale
    )

    if not result_bytes:
        raise HTTPException(500, "Background replacement generation failed.")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    filename = f"replacebg_{timestamp}.png"
    filepath = rt.image_edit.save_dir / filename
    try:
        with open(filepath, "wb") as f:
            f.write(result_bytes)
    except Exception as e:
        logger.warning(f"Failed to save replaced background image: {e}")

    b64_str = base64.b64encode(result_bytes).decode("utf-8")

    asset = rt.image_studio_db.add_asset(
        asset_type="edited",
        filepath=str(filepath),
        session_id=session_id,
        prompt=f"Replaced Background: {prompt}",
        model="tool:replace_background",
        parent_asset_id=parent_asset_id
    )

    return {
        "id": asset["id"],
        "image_base64": b64_str,
        "filepath": str(filepath),
        "source": "Local Background Replacement",
        "parent_asset_id": parent_asset_id
    }


@app.post("/api/image/outpaint")
async def outpaint_image_api(
    payload: Dict[str, Any] = Body(...),
    rt: JarvisRuntime = Depends(get_runtime)
):
    if not rt.image_edit or not rt.image_studio_db:
        raise HTTPException(500, "Image Studio engine not initialized.")

    image_b64 = payload.get("image")
    if not image_b64:
        raise HTTPException(400, "No image provided for outpainting.")

    prompt = payload.get("prompt", "")
    target_ratio = payload.get("target_ratio", "16:9")
    session_id = payload.get("session_id")
    parent_asset_id = payload.get("parent_asset_id")
    negative_prompt = payload.get("negative_prompt", "")
    denoising_strength = float(payload.get("denoising_strength", 0.90))
    steps = int(payload.get("steps", 25))
    cfg_scale = float(payload.get("cfg_scale", 7.0))

    try:
        from core.system_monitor import system_monitor
        system_monitor.park_for_media_generation()
    except Exception as e:
        logger.warning(f"Failed to park system monitor/Ollama for outpainting: {e}")

    result_bytes = await asyncio.to_thread(
        rt.image_edit.outpaint_image,
        image_b64,
        prompt,
        target_ratio,
        negative_prompt,
        denoising_strength,
        steps,
        cfg_scale
    )

    if not result_bytes:
        raise HTTPException(500, "Outpainting generation failed.")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    filename = f"outpaint_{timestamp}.png"
    filepath = rt.image_edit.save_dir / filename
    try:
        with open(filepath, "wb") as f:
            f.write(result_bytes)
    except Exception as e:
        logger.warning(f"Failed to save outpainted image: {e}")

    b64_str = base64.b64encode(result_bytes).decode("utf-8")

    asset = rt.image_studio_db.add_asset(
        asset_type="edited",
        filepath=str(filepath),
        session_id=session_id,
        prompt=f"Outpaint ({target_ratio}): {prompt}" if prompt else f"Outpaint ({target_ratio})",
        model="tool:outpaint",
        parent_asset_id=parent_asset_id
    )

    return {
        "id": asset["id"],
        "image_base64": b64_str,
        "filepath": str(filepath),
        "source": "Local Generative Outpaint",
        "parent_asset_id": parent_asset_id
    }


# ── GPU & Media Task Queue Telemetry Endpoints ─────────────────────────
@app.get("/api/gpu/queue")
async def get_gpu_media_queue(rt: JarvisRuntime = Depends(get_runtime)):
    if not rt.gpu_scheduler:
        raise HTTPException(500, "GPU scheduler not initialized.")
    return rt.gpu_scheduler.get_queue_snapshot()


@app.get("/api/gpu/queue/{job_id}")
async def get_media_job_status(job_id: str, rt: JarvisRuntime = Depends(get_runtime)):
    if not rt.gpu_scheduler:
        raise HTTPException(500, "GPU scheduler not initialized.")
    status = rt.gpu_scheduler.get_job_status(job_id)
    if not status:
        raise HTTPException(404, "Media job ID not found.")
    return status


# ── Imagine Video Studio Endpoints (V3 Motion Synthesis) ───────────────
@app.post("/api/video/generate")
async def generate_motion_video_api(
    payload: Dict[str, Any] = Body(...),
    rt: JarvisRuntime = Depends(get_runtime)
):
    if not rt.video_studio:
        raise HTTPException(500, "Video Studio engine not initialized.")

    image_b64 = payload.get("image")
    if not image_b64:
        raise HTTPException(400, "Keyframe image is required for motion video generation.")

    motion_type = payload.get("motion_type", "zoom_in")
    duration = float(payload.get("duration", 2.0))
    fps = int(payload.get("fps", 16))
    session_id = payload.get("session_id")
    parent_asset_id = payload.get("parent_asset_id")

    # Enroll in GPU Media Job Queue
    job_id = rt.gpu_scheduler.register_media_job("video_synthesis", {
        "motion_type": motion_type,
        "duration": duration,
        "fps": fps
    })
    rt.gpu_scheduler.update_job_status(job_id, "running", progress=0.2)

    try:
        video_bytes, vid_filepath = await asyncio.to_thread(
            rt.video_studio.generate_motion_video,
            image_b64,
            motion_type,
            duration,
            fps
        )
    except Exception as e:
        rt.gpu_scheduler.update_job_status(job_id, "failed", error=str(e))
        raise HTTPException(500, f"Video generation failed: {e}")

    if not video_bytes or not vid_filepath:
        rt.gpu_scheduler.update_job_status(job_id, "failed", error="Synthesis returned empty buffer")
        raise HTTPException(500, "Failed to synthesize motion video.")

    rt.gpu_scheduler.update_job_status(job_id, "completed", progress=1.0)

    b64_video = base64.b64encode(video_bytes).decode("utf-8")
    data_uri = f"data:video/mp4;base64,{b64_video}"

    # Also register in Studio DB as a distinct 'video' asset type with exact path
    asset_id = None
    if rt.image_studio_db:
        asset = rt.image_studio_db.add_asset(
            asset_type="video",
            filepath=vid_filepath,
            session_id=session_id,
            prompt=f"Motion Video ({motion_type}, {duration}s)",
            model="video:motion_synthesizer",
            parent_asset_id=parent_asset_id
        )
        asset_id = asset["id"]

    return {
        "id": asset_id,
        "job_id": job_id,
        "video_base64": b64_video,
        "video_uri": data_uri,
        "filepath": vid_filepath,
        "motion_type": motion_type,
        "duration": duration,
        "fps": fps,
        "source": "Local Imagine Video Engine"
    }


@app.get("/api/image/library")
async def get_image_library(
    type: Optional[str] = "all",
    favorite: bool = False,
    query: str = "",
    limit: int = 60,
    offset: int = 0,
    rt: JarvisRuntime = Depends(get_runtime)
):
    if not rt.image_studio_db:
        return {"assets": []}
    assets = rt.image_studio_db.list_assets(
        asset_type=type,
        favorite_only=favorite,
        search_query=query,
        limit=limit,
        offset=offset
    )
    for a in assets:
        fp = a.get("filepath")
        is_video = a.get("asset_type") == "video" or (fp and fp.endswith(".mp4"))
        # Do NOT load full video files as base64 into the library JSON payload
        # Frontend renders HTML5 video src directly via static mount
        if is_video:
            continue
        if fp and os.path.exists(fp):
            try:
                with open(fp, "rb") as f:
                    a["image_base64"] = base64.b64encode(f.read()).decode("utf-8")
            except Exception:
                pass
    return {"assets": assets}


@app.post("/api/image/library/{asset_id}/favorite")
async def toggle_library_favorite(asset_id: int, rt: JarvisRuntime = Depends(get_runtime)):
    if not rt.image_studio_db:
        raise HTTPException(500, "Studio DB not active")
    is_fav = rt.image_studio_db.toggle_favorite(asset_id)
    return {"id": asset_id, "is_favorite": is_fav}


@app.delete("/api/image/library/{asset_id}")
async def delete_library_asset(asset_id: int, rt: JarvisRuntime = Depends(get_runtime)):
    if not rt.image_studio_db:
        raise HTTPException(500, "Studio DB not active")
    rt.image_studio_db.delete_asset(asset_id)
    return {"status": "deleted", "id": asset_id}


def _generate_pollinations_direct(prompt: str, submodel: str = "turbo"):
    import urllib.parse
    import requests
    encoded = urllib.parse.quote(prompt.strip())
    url = f"https://image.pollinations.ai/prompt/{encoded}?nologo=true&model={submodel}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    for attempt in range(3):
        try:
            resp = requests.get(url, headers=headers, timeout=60)
            if resp.status_code == 200 and resp.content:
                return resp.content, f"Pollinations AI ({submodel})"
            elif resp.status_code in (402, 429, 503):
                time.sleep(4)
        except Exception as e:
            logger.warning(f"Pollinations attempt {attempt+1} failed: {e}")
            time.sleep(2)
    return None, f"Pollinations AI ({submodel}) (Failed)"


# ── Vision Endpoints ─────────────────────────────────────────────────
@app.get("/api/vision/screenshot")
async def take_screenshot(rt: JarvisRuntime = Depends(get_runtime)):
    try:
        import pyautogui
        import io
        img = pyautogui.screenshot()
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        img_b64 = base64.b64encode(buf.getvalue()).decode()

        desc = ""
        try:
            desc = await asyncio.to_thread(rt.vision.describe_screen)
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
async def describe_image(image: UploadFile = File(...), rt: JarvisRuntime = Depends(get_runtime)):
    try:
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp.write(await image.read())
            tmp_path = tmp.name
        desc = await asyncio.to_thread(rt.vision.describe_image, tmp_path)
        os.unlink(tmp_path)
        return {"description": desc}
    except Exception as e:
        raise HTTPException(500, str(e))


# ── Voice Transcription ──────────────────────────────────────────────
@app.post("/api/voice/transcribe")
async def transcribe_audio(audio: UploadFile = File(...)):
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
async def system_status(rt: JarvisRuntime = Depends(get_runtime)):
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

    sessions = rt.session_db.list_sessions()
    total_messages = sum(s.get("message_count", 0) for s in sessions)

    system_drive = os.environ.get("SystemDrive", "C:") + "\\"
    return {
        "cpu_percent": psutil.cpu_percent(),
        "ram_percent": psutil.virtual_memory().percent,
        "gpu_vram_percent": gpu_pct,
        "disk_percent": psutil.disk_usage(system_drive).percent,
        "jarvis_state": "idle",
        "uptime": f"{int(time.time() - START_TIME)}s",
        "session_count": len(sessions),
        "total_messages": total_messages,
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
async def create_api_key(req: APIKeyCreateRequest, rt: JarvisRuntime = Depends(get_runtime)):
    return rt.key_mgr.create_key(req.name, req.permissions, req.rate_limit)


@app.get("/api/keys")
async def list_api_keys(rt: JarvisRuntime = Depends(get_runtime)):
    return rt.key_mgr.list_keys()


@app.delete("/api/keys/{key_id}")
async def revoke_api_key(key_id: str, rt: JarvisRuntime = Depends(get_runtime)):
    ok = rt.key_mgr.revoke_key(key_id)
    if not ok:
        raise HTTPException(404, "Key not found")
    return {"revoked": key_id}


@app.post("/api/keys/{key_id}/rotate")
async def rotate_api_key(key_id: str, rt: JarvisRuntime = Depends(get_runtime)):
    result = rt.key_mgr.rotate_key(key_id)
    if not result:
        raise HTTPException(404, "Key not found")
    return result


# ═══════════════════════════════════════════════════════════════════════
# WEBSOCKET ENDPOINT
# ═══════════════════════════════════════════════════════════════════════

@app.websocket("/ws/{session_id}")
async def websocket_endpoint(ws: WebSocket, session_id: str):
    # Authenticate WebSocket handshake via query param or header
    token = ws.query_params.get("token") or ws.headers.get("x-auth-token")
    if not token or token != LOCAL_AUTH_TOKEN:
        logger.warning(f"Rejecting unauthenticated WebSocket connection to session: {session_id}")
        await ws.close(code=1008)  # Policy Violation
        return

    rt: JarvisRuntime = ws.app.state.jarvis
    await rt.manager.connect(ws, session_id)
    rt.session_db.create_session(session_id)

    try:
        while True:
            data = await ws.receive_json()
            event_type = data.get("type")

            if event_type == "message":
                content = data.get("content", "")
                if not content:
                    continue

                # Append user message to SQLite
                rt.session_db.add_message(session_id, "user", content)

                # Route message through UnifiedAgentOrchestrator
                sess = rt.session_db.get_session(session_id)
                history = sess.get("messages", [])[:-1] if sess else []

                response_text = ""
                try:
                    if rt.orchestrator:
                        response_text = await rt.orchestrator.execute_task(
                            query=content,
                            conversation_history=history,
                            session_id=session_id,
                            step_callback=lambda step: rt.manager.send_to_session(session_id, {"type": "agent_step", "step": step})
                        )
                    else:
                        ctx = await asyncio.to_thread(rt.memory.get_relevant_context, content)
                        messages = _build_messages(rt.session_db, session_id, content, ctx)
                        response_text = await asyncio.to_thread(rt.llm.generate, messages, False)
                except Exception as e:
                    logger.error(f"WS Orchestration failed: {e}", exc_info=True)
                    response_text = f"I encountered an issue processing your request, sir: {e}"

                # Send completion event
                await ws.send_json({
                    "type": "complete",
                    "content": response_text,
                })

                # Append response to SQLite
                rt.session_db.add_message(session_id, "jarvis", response_text)

                # Auto-title on first conversation turn
                sess = rt.session_db.get_session(session_id)
                if sess and len(sess.get("messages", [])) == 2:
                    try:
                        title = await asyncio.to_thread(
                            rt.llm.generate,
                            [{"role": "user", "content":
                              f"Give this conversation a short 4-word title: {content}"}],
                            False, False, config.FAST_MODEL
                        )
                        clean_title = title.strip().strip('"').strip("'")[:50]
                        rt.session_db.update_title(session_id, clean_title)
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
        rt.manager.disconnect(ws, session_id)


# ═══════════════════════════════════════════════════════════════════════
# STARTUP & RUN (Lifespan — replaces deprecated @app.on_event)
# ═══════════════════════════════════════════════════════════════════════

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(application: FastAPI):
    """Modern lifespan event handler: initialises JarvisRuntime on startup."""
    logger.info("JARVIS API server initializing runtime container...")
    runtime = JarvisRuntime()
    await runtime.boot()
    application.state.jarvis = runtime
    logger.info("JARVIS API ready on http://127.0.0.1:8080")
    yield
    # Shutdown phase (currently nothing to clean up)

app.router.lifespan_context = None


# Mount HUD static files
hud_dir = JARVIS_ROOT / "hud"
if hud_dir.exists():
    app.mount("/hud", StaticFiles(directory=str(hud_dir), html=True), name="hud")

# Mount storage directory for serving images, videos, and other media assets
storage_dir = JARVIS_ROOT / "storage"
if storage_dir.exists():
    app.mount("/storage", StaticFiles(directory=str(storage_dir)), name="storage")


if __name__ == "__main__":
    uvicorn.run(
        "api_server:app",
        host="127.0.0.1",
        port=8080,
        reload=False,
        log_level="info",
    )
