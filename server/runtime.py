"""
server/runtime.py — JARVIS Unified Application Runtime Container (V2.1 Hardened)
================================================================================
Single-source-of-truth for all JARVIS module singletons.
Eliminates fragmented module-level globals by holding every engine,
memory tier, registry, and manager in one strongly-typed container
attached to FastAPI's `app.state.jarvis`.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Optional

import config
from modules.llm import IntelligentLLMEngine
from modules.stt import SpeechToText
from modules.tts import StreamingTextToSpeech
from modules.intent import DualModelIntentClassifier
from modules.long_term_memory import HybridRAGMemory
from modules.automation import AutomationEngine
from modules.email_handler import EmailHandler
from modules.whatsapp_handler import WhatsAppHandler
from modules.web_search import WebSearchEngine
from modules.weather import get_weather
from modules.news import get_news
from modules.scheduler import ReminderScheduler
from modules.document_reader import DocumentReader
from modules.iot_handler import IoTHandler
from modules.vision import VisionEngine
from modules.code_engine import CodeEngine
from modules.image_gen import ImageGenerationEngine
from modules.image_edit import ImageEditEngine
from modules.image_studio_db import ImageStudioDB
from modules.video_studio import VideoStudioEngine
from modules.security.permission_engine import PermissionEngine, ActionCategory
from modules.agent.tool_registry import (
    StructuredToolRegistry,
    OpenAppInput,
    CloseAppInput,
    FocusWindowInput,
    BrowsePageInput,
    ExecuteCodeInput,
    SearchMemoryInput,
    EmptyInput,
    SendEmailInput,
    ReadEmailInput,
    SendWhatsAppInput,
    WebSearchInput,
    WeatherInput,
    NewsInput,
    SetReminderInput,
    ReadDocumentInput,
    SmartHomeControlInput,
    DeepResearchInput,
    CodeProposalInput,
    IngestDocumentInput,
)
from modules.agent.orchestrator import UnifiedAgentOrchestrator
from modules.agent.research_agent import DeepResearchAgent
from modules.agent.coding_agent import AutonomousCodingAgent
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


@dataclass
class JarvisRuntime:
    """Holds every initialised JARVIS module singleton."""

    # ── Infrastructure ────────────────────────────────────────────
    manager: ConnectionManager = field(default_factory=ConnectionManager)
    key_mgr: APIKeyManager = field(default_factory=APIKeyManager)
    session_db: SessionDatabase = field(default_factory=SessionDatabase)

    # ── Security & Registries ─────────────────────────────────────
    permission_engine: PermissionEngine = field(default_factory=PermissionEngine)
    tool_registry: StructuredToolRegistry = field(default_factory=StructuredToolRegistry)
    task_manager: PersistentTaskManager = field(default_factory=PersistentTaskManager)
    skill_registry: DynamicSkillRegistry = field(default_factory=DynamicSkillRegistry)
    mcp_manager: PluginManager = field(default_factory=PluginManager)
    gpu_scheduler: GPUScheduler = field(default_factory=GPUScheduler)

    # ── Computer Use ──────────────────────────────────────────────
    computer_use: WindowsComputerUse = field(default_factory=WindowsComputerUse)
    browser_agent: PlaywrightBrowserAgent = field(default_factory=PlaywrightBrowserAgent)

    # ── Core AI Engines (lazy — set in boot()) ────────────────────
    llm: Optional[IntelligentLLMEngine] = None
    tts: Optional[StreamingTextToSpeech] = None
    stt: Optional[SpeechToText] = None
    intent: Optional[DualModelIntentClassifier] = None
    memory: Optional[HybridRAGMemory] = None
    four_tier_memory: Optional[FourTierMemorySystem] = None
    vision: Optional[VisionEngine] = None
    automation: Optional[AutomationEngine] = None
    email_h: Optional[EmailHandler] = None
    whatsapp_h: Optional[WhatsAppHandler] = None
    web_search_e: Optional[WebSearchEngine] = None
    scheduler_h: Optional[ReminderScheduler] = None
    doc_reader: Optional[DocumentReader] = None
    iot_h: Optional[IoTHandler] = None
    code_e: Optional[CodeEngine] = None
    image_gen: Optional[ImageGenerationEngine] = None
    image_edit: Optional[ImageEditEngine] = None
    image_studio_db: Optional[ImageStudioDB] = None
    video_studio: Optional[VideoStudioEngine] = None

    # ── Agent Layer ───────────────────────────────────────────────
    orchestrator: Optional[UnifiedAgentOrchestrator] = None
    workflow_engine: Optional[AutonomousWorkflowEngine] = None
    research_agent: Optional[DeepResearchAgent] = None
    coding_agent: Optional[AutonomousCodingAgent] = None

    async def boot(self) -> None:
        """
        Initialise all AI modules, register tools, wire up the orchestrator
        and workflow engine. Called once from FastAPI startup.
        """
        logger.info("JARVIS Runtime booting...")

        # ── Core AI Engines ────────────────────────────────────────
        self.llm = IntelligentLLMEngine(
            config.JARVIS_SYSTEM_PROMPT,
            stream_callback=lambda t: asyncio.create_task(
                self.manager.broadcast_token(t)
            ),
            state_callback=lambda s: asyncio.create_task(
                self.manager.broadcast_state(s)
            ),
            gpu_scheduler=self.gpu_scheduler,
        )
        self.tts = StreamingTextToSpeech()
        self.stt = SpeechToText()
        self.intent = DualModelIntentClassifier(self.llm)
        self.memory = HybridRAGMemory(self.llm)
        self.four_tier_memory = FourTierMemorySystem(self.memory)
        self.vision = VisionEngine()
        self.automation = AutomationEngine()
        self.email_h = EmailHandler()
        self.whatsapp_h = WhatsAppHandler()
        self.web_search_e = WebSearchEngine()
        self.scheduler_h = ReminderScheduler(tts_callback=self.tts.speak if hasattr(self, 'tts') else None)
        self.doc_reader = DocumentReader()
        self.iot_h = IoTHandler()
        self.code_e = CodeEngine()

        try:
            self.image_gen = ImageGenerationEngine()
            self.image_edit = ImageEditEngine()
            self.image_studio_db = ImageStudioDB(db_path=str(config.DATA_DIR / "image_studio.db"))
            self.video_studio = VideoStudioEngine()
        except Exception as e:
            logger.warning(f"Could not initialize ImageGenerationEngine / Studio: {e}")

        # ── Wire Permission Approval Callback to WebSocket Broadcast ──
        async def ui_approval_callback(action: str, details: dict, session_id: Optional[str] = None, **kw) -> bool:
            import uuid
            request_id = str(uuid.uuid4())
            fut = self.permission_engine.register_approval_request(request_id)
            
            # Target specific session if known and active.
            # Security Rule: Fail closed if target session is missing or offline.
            # Do NOT broadcast sensitive approval prompts to arbitrary connected sessions.
            if not session_id or session_id not in self.manager.active:
                logger.warning(
                    f"Approval request {request_id} for '{action}' rejected: "
                    f"originating session '{session_id}' is unavailable or inactive (fail-closed)."
                )
                return False

            target_sessions = [session_id]

            payload = {
                "type": "approval_required",
                "request_id": request_id,
                "action": action,
                "details": details
            }
            logger.info(f"Emitting approval request to session {session_id}: {payload}")
            await self.manager.send_to_session(session_id, payload)

            # Wait for user decision with 45s timeout
            try:
                approved = await asyncio.wait_for(fut, timeout=45.0)
                return approved
            except asyncio.TimeoutError:
                logger.warning(f"Approval request {request_id} timed out.")
                return False

        self.permission_engine.set_approval_callback(ui_approval_callback)

        # ── Register Canonical Tools ───────────────────────────────
        self._register_canonical_tools()

        # ── Mount Dynamic Skills ───────────────────────────────────
        self.skill_registry.discover_and_mount(self.tool_registry)

        # ── MCP Plugins ────────────────────────────────────────────
        try:
            self.mcp_manager.start_all()
            for mcp_tool in self.mcp_manager._all_tools:
                _server = mcp_tool.server_name
                _name = mcp_tool.name
                self.tool_registry.register(
                    name=f"mcp__{_server}__{_name}",
                    description=f"[MCP:{_server}] {mcp_tool.description}",
                    func=lambda _s=_server, _n=_name, **kw: self.mcp_manager.clients[_s].call_tool(_n, kw),
                    risk="medium",
                    permission_category="mcp_call"
                )
        except Exception as e:
            logger.warning(f"MCP Plugin auto-start: {e}")

        # ── Orchestrator ───────────────────────────────────────────
        self.orchestrator = UnifiedAgentOrchestrator(
            llm=self.llm,
            tools=self.tool_registry,
            memory=self.memory,
            permission_engine=self.permission_engine,
            four_tier_memory=self.four_tier_memory,
        )

        # ── Specialized Intelligence Agents ────────────────────────
        self.research_agent = DeepResearchAgent(
            llm=self.llm,
            web_search_engine=self.web_search_e,
            browser_agent=self.browser_agent
        )
        self.coding_agent = AutonomousCodingAgent(
            llm=self.llm,
            code_engine=self.code_e
        )

        # ── Workflow Engine ────────────────────────────────────────
        self.workflow_engine = AutonomousWorkflowEngine(
            orchestrator=self.orchestrator,
            task_manager=self.task_manager,
        )

        # Start GPU Scheduler background queue worker
        self.gpu_scheduler.start_worker()

        # ── Startup Recovery: Clean up interrupted tasks from previous session ──
        recovered = self.task_manager.recover_interrupted_tasks()
        if recovered:
            logger.info(f"Startup task recovery: cleaned {len(recovered)} interrupted task(s).")

        logger.info("JARVIS Runtime boot complete — canonical tools and security gate online.")

    # ──────────────────────────────────────────────────────────────
    def _register_canonical_tools(self) -> None:
        """Register all tools with strongly-typed Pydantic schemas and aligned categories."""
        reg = self.tool_registry

        reg.register(
            name="open_app",
            description="Launch or open a desktop application by name",
            func=lambda app_name: self.automation.open_app(app_name),
            schema_cls=OpenAppInput,
            risk="medium",
            permission_category=ActionCategory.OPEN_APPLICATION
        )

        reg.register(
            name="close_app",
            description="Close an active desktop application by name",
            func=lambda app_name: self.automation.close_app(app_name),
            schema_cls=CloseAppInput,
            risk="medium",
            permission_category=ActionCategory.CLOSE_APPLICATION
        )

        reg.register(
            name="system_status",
            description="Check system CPU, RAM, Disk, and hardware metrics",
            func=lambda: self.automation.get_system_status(),
            schema_cls=EmptyInput,
            risk="low",
            permission_category=ActionCategory.SYSTEM_STATUS
        )

        reg.register(
            name="take_screenshot",
            description="Capture current primary screen display",
            func=lambda: self.automation.take_screenshot(),
            schema_cls=EmptyInput,
            risk="low",
            permission_category=ActionCategory.TAKE_SCREENSHOT
        )

        reg.register(
            name="describe_screen",
            description="Analyze and describe what is visible on current display",
            func=lambda: self.vision.describe_screen(),
            schema_cls=EmptyInput,
            risk="low",
            permission_category=ActionCategory.DESCRIBE_SCREEN
        )

        reg.register(
            name="search_memory",
            description="Search past conversation memory, user preferences, and facts",
            func=lambda query: self.memory.get_relevant_context(query),
            schema_cls=SearchMemoryInput,
            risk="low",
            permission_category=ActionCategory.SEARCH_MEMORY
        )

        reg.register(
            name="execute_code",
            description="Execute Python code in isolated process sandbox",
            func=lambda code: self.code_e.execute_python(code),
            schema_cls=ExecuteCodeInput,
            risk="high",
            permission_category=ActionCategory.EXECUTE_CODE
        )

        reg.register(
            name="list_windows",
            description="List all open desktop application windows",
            func=lambda: self.computer_use.list_open_windows(),
            schema_cls=EmptyInput,
            risk="low",
            permission_category=ActionCategory.LIST_WINDOWS
        )

        reg.register(
            name="focus_window",
            description="Switch focus to a specific desktop application window",
            func=lambda window_name: self.computer_use.focus_window(window_name),
            schema_cls=FocusWindowInput,
            risk="medium",
            permission_category=ActionCategory.FOCUS_WINDOW
        )

        reg.register(
            name="browse_page",
            description="Headlessly fetch clean page text without taking mouse focus",
            func=lambda url: asyncio.run(self.browser_agent.fetch_page_content(url)),
            schema_cls=BrowsePageInput,
            risk="medium",
            permission_category=ActionCategory.BROWSE_URL
        )

        # ── Legacy & Parity Restored Tools ─────────────────────────
        reg.register(
            name="send_email",
            description="Send an email to a recipient address",
            func=lambda to, subject, body: self.email_h.send(to=to, subject=subject, body=body) if self.email_h else False,
            schema_cls=SendEmailInput,
            risk="high",
            permission_category="send_email"
        )

        reg.register(
            name="read_email",
            description="Read recent emails from the user's inbox",
            func=lambda count=5: self.email_h.read_inbox(count=count) if self.email_h else "Email handler not available",
            schema_cls=ReadEmailInput,
            risk="low",
            permission_category="read_file"
        )

        reg.register(
            name="send_whatsapp",
            description="Send a message to a WhatsApp phone number",
            func=lambda phone_number, message: self.whatsapp_h.send(phone_number=phone_number, message=message) if self.whatsapp_h else False,
            schema_cls=SendWhatsAppInput,
            risk="high",
            permission_category="send_whatsapp"
        )

        reg.register(
            name="web_search",
            description="Perform a live web search and return structured answers",
            func=lambda query: self.web_search_e.search_and_answer(query) if self.web_search_e else "Web search not available",
            schema_cls=WebSearchInput,
            risk="low",
            permission_category="search_web"
        )

        reg.register(
            name="get_weather",
            description="Get current weather information for a specified location",
            func=lambda location="": get_weather(location=location),
            schema_cls=WeatherInput,
            risk="low",
            permission_category="answer_question"
        )

        reg.register(
            name="get_news",
            description="Retrieve top current news headlines",
            func=lambda count=5: get_news(count=count),
            schema_cls=NewsInput,
            risk="low",
            permission_category="answer_question"
        )

        reg.register(
            name="set_reminder",
            description="Schedule a reminder task for a given time",
            func=lambda time_str, task: self.scheduler_h.add_reminder(time_str=time_str, task=task) if self.scheduler_h else "Scheduler not available",
            schema_cls=SetReminderInput,
            risk="low",
            permission_category="answer_question"
        )

        reg.register(
            name="read_document",
            description="Read and extract text content from a PDF, DOCX, or text file",
            func=lambda file_path: self.doc_reader.read(file_path) if self.doc_reader else "Document reader not available",
            schema_cls=ReadDocumentInput,
            risk="low",
            permission_category="read_file"
        )

        reg.register(
            name="smart_home_control",
            description="Control a smart home device or perform an IoT action",
            func=lambda device, action: self.iot_h.control_device(device=device, action=action) if self.iot_h else "IoT handler not available",
            schema_cls=SmartHomeControlInput,
            risk="medium",
            permission_category="modify_system_settings"
        )

        # ── Advanced Intelligence Tools ───────────────────────────
        reg.register(
            name="deep_research",
            description="Perform multi-query web research, cross-reference sources, and compile citations",
            func=lambda topic, max_subqueries=3: asyncio.run(self.research_agent.conduct_research(topic, max_subqueries=max_subqueries)) if self.research_agent else "Research agent unavailable",
            schema_cls=DeepResearchInput,
            risk="low",
            permission_category="search_web",
            timeout=60
        )

        reg.register(
            name="propose_code_fix",
            description="Inspect a local file, draft a syntax-validated code change or bug fix proposal",
            func=lambda target_file, task_instruction: asyncio.run(self.coding_agent.propose_and_verify_fix(task_instruction, target_file)) if self.coding_agent else "Coding agent unavailable",
            schema_cls=CodeProposalInput,
            risk="medium",
            permission_category="modify_code",
            timeout=45
        )

        reg.register(
            name="ingest_document",
            description="Ingest, chunk, and index a document (PDF, DOCX, TXT) into Semantic RAG ChromaDB",
            func=lambda file_path: f"Ingested {self.doc_reader.ingest_to_memory(file_path, self.memory)} chunks into Semantic RAG." if self.doc_reader and self.memory else "Ingestion unavailable",
            schema_cls=IngestDocumentInput,
            risk="low",
            permission_category="read_file",
            timeout=30
        )
