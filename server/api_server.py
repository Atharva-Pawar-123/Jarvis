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
from typing import Optional, List

from fastapi import (
    FastAPI, WebSocket, WebSocketDisconnect, HTTPException,
    UploadFile, File, Header, Request, Depends
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
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
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
        "version": "3.1",
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
        authorized, reason = await rt.permission_engine.verify_and_authorize(intent_name, {"query": req.content})
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
        rt.memory.facts_col.delete(ids=[fact_id])
        return {"deleted": fact_id}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/memory/clear")
async def clear_memory(x_confirm: Optional[str] = Header(None), rt: JarvisRuntime = Depends(get_runtime)):
    if x_confirm != "CLEAR_ALL_MEMORY":
        raise HTTPException(403, "Missing confirmation header: X-Confirm: CLEAR_ALL_MEMORY")
    try:
        rt.memory.facts_col.delete(where={})
        rt.memory.convs_col.delete(where={})
        rt.memory.docs_col.delete(where={})
        return {"cleared": True}
    except Exception as e:
        raise HTTPException(500, str(e))


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
async def list_image_models():
    """List available image generation models explicitly without auto fallback."""
    models = []

    # 1. Local Forge Models (Detected or Default Checkpoint)
    forge_detected = False
    try:
        import requests
        forge_url = getattr(config, "SD_LOCAL_URL", "http://127.0.0.1:7860")
        resp = requests.get(f"{forge_url}/sdapi/v1/sd-models", timeout=1.5)
        if resp.status_code == 200:
            for item in resp.json():
                title = item.get("title") or item.get("model_name") or "Local Model"
                models.append({
                    "id": f"local:{title}",
                    "name": f"{title} (Local SD Forge)",
                    "source": "forge",
                    "description": f"Local GPU checkpoint: {item.get('filename', title)}"
                })
            forge_detected = True
    except Exception:
        pass

    if not forge_detected:
        models.append({
            "id": "local",
            "name": "DreamShaper 8 (Local SD Forge)",
            "source": "forge",
            "description": "Local SD Forge running DreamShaper 8 on NVIDIA RTX GPU"
        })

    # 2. Specific Cloud Pollinations AI Models
    models.extend([
        {
            "id": "pollinations:turbo",
            "name": "Pollinations Turbo (Cloud)",
            "source": "pollinations",
            "description": "Fast generation with clean prompt adherence"
        },
        {
            "id": "pollinations:flux",
            "name": "FLUX.1 Schnell (Cloud)",
            "source": "pollinations",
            "description": "State-of-the-art open weights model with exceptional photorealism"
        },
        {
            "id": "pollinations:flux-realism",
            "name": "FLUX Realism (Cloud)",
            "source": "pollinations",
            "description": "Tuned specifically for realistic lighting, skin textures, and portraits"
        },
        {
            "id": "pollinations:flux-anime",
            "name": "FLUX Anime (Cloud)",
            "source": "pollinations",
            "description": "Specialized artistic anime and illustration styling"
        }
    ])

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

    img_bytes = None
    source = "Unknown"
    model_choice = req.model or "local"

    # GPU VRAM Coordination: park Ollama models before local SD Forge generation
    if model_choice == "local" or model_choice.startswith("local:"):
        try:
            await rt.gpu_scheduler.prepare_for_image_gen()
        except Exception as e:
            logger.warning(f"GPU scheduler park failed: {e}")

        img_bytes = await asyncio.to_thread(
            rt.image_gen._generate_local,
            working_prompt,
            req.negative_prompt or "",
            req.steps or 20,
            req.width or 512,
            req.height or 512
        )
        if img_bytes:
            source = f"Local SD ({model_choice})"
        else:
            raise HTTPException(503, "Local Stable Diffusion Forge is offline or failed to generate. Please ensure Forge is running on port 7860.")

    elif model_choice.startswith("pollinations") or model_choice == "pollinations":
        # Extract sub-model if specified (e.g. pollinations:flux -> flux)
        submodel = "turbo"
        if ":" in model_choice:
            submodel = model_choice.split(":", 1)[1]
        img_bytes, source = await asyncio.to_thread(_generate_pollinations_direct, working_prompt, submodel)
        if not img_bytes:
            raise HTTPException(502, f"Pollinations AI ({submodel}) failed to generate the image.")

    else:
        # Default to local
        img_bytes = await asyncio.to_thread(
            rt.image_gen._generate_local,
            working_prompt,
            req.negative_prompt or "",
            req.steps or 20,
            req.width or 512,
            req.height or 512
        )
        source = "Local SD" if img_bytes else "Unknown"

    if not img_bytes:
        raise HTTPException(500, "Image generation failed on selected engine.")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    filename = f"gen_{timestamp}.png"
    filepath = rt.image_gen.save_dir / filename
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
# STARTUP & RUN
# ═══════════════════════════════════════════════════════════════════════

@app.on_event("startup")
async def startup():
    logger.info("JARVIS API server initializing runtime container...")
    runtime = JarvisRuntime()
    await runtime.boot()
    app.state.jarvis = runtime
    logger.info("JARVIS API ready on http://127.0.0.1:8080")


# Mount HUD static files
hud_dir = JARVIS_ROOT / "hud"
if hud_dir.exists():
    app.mount("/hud", StaticFiles(directory=str(hud_dir), html=True), name="hud")


if __name__ == "__main__":
    uvicorn.run(
        "api_server:app",
        host="127.0.0.1",
        port=8080,
        reload=False,
        log_level="info",
    )
