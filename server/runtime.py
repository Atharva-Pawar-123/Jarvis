"""
server/runtime.py — JARVIS Unified Application Runtime Container
=================================================================
Single-source-of-truth for all JARVIS module singletons.
Eliminates fragmented module-level globals by holding every engine,
memory tier, registry, and manager in one strongly-typed container
attached to FastAPI's `app.state.jarvis`.

Usage in any endpoint:
    runtime: JarvisRuntime = request.app.state.jarvis
    runtime.llm.generate(...)
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
from modules.vision import VisionEngine
from modules.code_engine import CodeEngine
from modules.image_gen import ImageGenerationEngine
from modules.security.permission_engine import PermissionEngine
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
    code_e: Optional[CodeEngine] = None
    image_gen: Optional[ImageGenerationEngine] = None

    # ── Agent Layer ───────────────────────────────────────────────
    orchestrator: Optional[UnifiedAgentOrchestrator] = None
    workflow_engine: Optional[AutonomousWorkflowEngine] = None

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
        )
        self.tts = StreamingTextToSpeech()
        self.stt = SpeechToText()
        self.intent = DualModelIntentClassifier(self.llm)
        self.memory = HybridRAGMemory(self.llm)
        self.four_tier_memory = FourTierMemorySystem(self.memory)
        self.vision = VisionEngine()
        self.automation = AutomationEngine()
        self.email_h = EmailHandler()
        self.code_e = CodeEngine()

        try:
            self.image_gen = ImageGenerationEngine()
        except Exception as e:
            logger.warning(f"Could not initialize ImageGenerationEngine: {e}")

        # ── Register Tools ─────────────────────────────────────────
        self._register_builtin_tools()

        # ── Mount Dynamic Skills ───────────────────────────────────
        self.skill_registry.discover_and_mount(self.tool_registry)

        # ── MCP Plugins ────────────────────────────────────────────
        try:
            self.mcp_manager.start_all()
            for mcp_tool in self.mcp_manager._all_tools:
                # Capture loop variable safely
                _server = mcp_tool.server_name
                _name = mcp_tool.name
                self.tool_registry.register(
                    name=f"mcp__{_server}__{_name}",
                    description=f"[MCP:{_server}] {mcp_tool.description}",
                    func=lambda _s=_server, _n=_name, **kw: self.mcp_manager.clients[_s].call_tool(_n, kw),
                    risk="medium",
                )
        except Exception as e:
            logger.warning(f"MCP Plugin auto-start: {e}")

        # ── Orchestrator ───────────────────────────────────────────
        self.orchestrator = UnifiedAgentOrchestrator(
            llm=self.llm,
            tools=self.tool_registry,
            memory=self.memory,
            permission_engine=self.permission_engine,
        )

        # ── Workflow Engine ────────────────────────────────────────
        self.workflow_engine = AutonomousWorkflowEngine(
            orchestrator=self.orchestrator,
            task_manager=self.task_manager,
        )

        logger.info("JARVIS Runtime boot complete — all modules online.")

    # ──────────────────────────────────────────────────────────────
    def _register_builtin_tools(self) -> None:
        """Register core JARVIS tools into the StructuredToolRegistry."""
        reg = self.tool_registry

        reg.register("open_app", "Launch or open a desktop app",
                      lambda app_name: self.automation.open_app(app_name))
        reg.register("close_app", "Close an active desktop application",
                      lambda app_name: self.automation.close_app(app_name))
        reg.register("system_status", "Check system CPU, RAM, Disk, and metrics",
                      lambda: self.automation.get_system_status())
        reg.register("take_screenshot", "Capture screen image",
                      lambda: self.automation.take_screenshot())
        reg.register("describe_screen", "Analyze and describe what is visible on display",
                      lambda: self.vision.describe_screen())
        reg.register("search_memory", "Search past conversation memory and stored facts",
                      lambda query: self.memory.get_relevant_context(query))
        reg.register("execute_code", "Execute Python code in isolated sandbox",
                      lambda code: self.code_e.execute_python(code), risk="high")
        reg.register("list_windows", "List all open desktop application windows",
                      lambda: self.computer_use.list_open_windows())
        reg.register("focus_window", "Switch focus to a specific desktop application window",
                      lambda window_name: self.computer_use.focus_window(window_name))
        reg.register("browse_page", "Headlessly fetch clean page text without taking mouse focus",
                      lambda url: asyncio.run(self.browser_agent.fetch_page_content(url)))
