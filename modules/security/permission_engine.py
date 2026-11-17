"""
modules/security/permission_engine.py — JARVIS Central Action-Risk Permission Gate
================================================================================
Enforces least privilege and human-in-the-loop control for all JARVIS actions.
Normalizes tool names, manages pending approval requests with WebSocket emission,
and provides async approval resolution.
"""

import enum
import logging
import asyncio
import uuid
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class RiskLevel(str, enum.Enum):
    LOW = "low"            # Read-only, informational, calculations
    MEDIUM = "medium"      # Scoped file writes, safe local actions
    HIGH = "high"          # External communication, file deletions, code execution, system power


class ActionCategory:
    # High Risk Actions (Always require approval or strict policy)
    SEND_EMAIL = "send_email"
    SEND_WHATSAPP = "send_whatsapp"
    DELETE_FILE = "delete_file"
    EXECUTE_CODE = "execute_code"
    SYSTEM_SHUTDOWN = "system_shutdown"
    SYSTEM_RESTART = "system_restart"
    MODIFY_SYSTEM_SETTINGS = "modify_system_settings"

    # Medium Risk
    WRITE_FILE = "write_file"
    OPEN_APPLICATION = "open_application"
    CLOSE_APPLICATION = "close_application"
    BROWSE_URL = "browse_url"
    FOCUS_WINDOW = "focus_window"

    # Low / Automatic
    ANSWER_QUESTION = "answer_question"
    SEARCH_WEB = "search_web"
    READ_FILE = "read_file"
    DRAFT_EMAIL = "draft_email"
    DRAFT_WHATSAPP = "draft_whatsapp"
    SYSTEM_STATUS = "system_status"
    LIST_FILES = "list_files"
    TAKE_SCREENSHOT = "take_screenshot"
    DESCRIBE_SCREEN = "describe_screen"
    SEARCH_MEMORY = "search_memory"
    LIST_WINDOWS = "list_windows"
    CALCULATE = "calculate"


# Normalization mapping: tool names to canonical ActionCategory
TOOL_TO_CATEGORY: Dict[str, str] = {
    "open_app": ActionCategory.OPEN_APPLICATION,
    "open_application": ActionCategory.OPEN_APPLICATION,
    "close_app": ActionCategory.CLOSE_APPLICATION,
    "close_application": ActionCategory.CLOSE_APPLICATION,
    "browse_page": ActionCategory.BROWSE_URL,
    "browse_url": ActionCategory.BROWSE_URL,
    "execute_code": ActionCategory.EXECUTE_CODE,
    "take_screenshot": ActionCategory.TAKE_SCREENSHOT,
    "describe_screen": ActionCategory.DESCRIBE_SCREEN,
    "search_memory": ActionCategory.SEARCH_MEMORY,
    "list_windows": ActionCategory.LIST_WINDOWS,
    "focus_window": ActionCategory.FOCUS_WINDOW,
    "system_status": ActionCategory.SYSTEM_STATUS,
    "send_email": ActionCategory.SEND_EMAIL,
    "send_whatsapp": ActionCategory.SEND_WHATSAPP,
    "delete_file": ActionCategory.DELETE_FILE,
    "skill_calculator": ActionCategory.CALCULATE,
}


# Default Policies: Action -> (RiskLevel, requires_explicit_approval)
DEFAULT_ACTION_POLICIES: Dict[str, tuple[RiskLevel, bool]] = {
    # Automatic (Safe)
    ActionCategory.ANSWER_QUESTION: (RiskLevel.LOW, False),
    ActionCategory.SEARCH_WEB: (RiskLevel.LOW, False),
    ActionCategory.READ_FILE: (RiskLevel.LOW, False),
    ActionCategory.DRAFT_EMAIL: (RiskLevel.LOW, False),
    ActionCategory.DRAFT_WHATSAPP: (RiskLevel.LOW, False),
    ActionCategory.SYSTEM_STATUS: (RiskLevel.LOW, False),
    ActionCategory.LIST_FILES: (RiskLevel.LOW, False),
    ActionCategory.TAKE_SCREENSHOT: (RiskLevel.LOW, False),
    ActionCategory.DESCRIBE_SCREEN: (RiskLevel.LOW, False),
    ActionCategory.SEARCH_MEMORY: (RiskLevel.LOW, False),
    ActionCategory.LIST_WINDOWS: (RiskLevel.LOW, False),
    ActionCategory.CALCULATE: (RiskLevel.LOW, False),

    # Medium / Scoped
    ActionCategory.WRITE_FILE: (RiskLevel.MEDIUM, False),
    ActionCategory.OPEN_APPLICATION: (RiskLevel.MEDIUM, False),
    ActionCategory.CLOSE_APPLICATION: (RiskLevel.MEDIUM, False),
    ActionCategory.BROWSE_URL: (RiskLevel.MEDIUM, False),
    ActionCategory.FOCUS_WINDOW: (RiskLevel.MEDIUM, False),

    # High Risk (Requires User Approval by Default)
    ActionCategory.SEND_EMAIL: (RiskLevel.HIGH, True),
    ActionCategory.SEND_WHATSAPP: (RiskLevel.HIGH, True),
    ActionCategory.DELETE_FILE: (RiskLevel.HIGH, True),
    ActionCategory.EXECUTE_CODE: (RiskLevel.HIGH, True),
    ActionCategory.SYSTEM_SHUTDOWN: (RiskLevel.HIGH, True),
    ActionCategory.SYSTEM_RESTART: (RiskLevel.HIGH, True),
    ActionCategory.MODIFY_SYSTEM_SETTINGS: (RiskLevel.HIGH, True),
}


class PermissionEngine:
    """Central permission checker and human-in-the-loop coordinator."""

    def __init__(self, approval_callback=None):
        self.policies = dict(DEFAULT_ACTION_POLICIES)
        self.approval_callback = approval_callback
        self.session_approvals: set[str] = set()
        # Pending interactive requests: request_id -> asyncio.Future
        self._pending_requests: Dict[str, asyncio.Future] = {}

    def set_approval_callback(self, callback):
        self.approval_callback = callback

    def normalize_action(self, action: str) -> str:
        """Translates arbitrary tool identifiers into canonical ActionCategory."""
        return TOOL_TO_CATEGORY.get(action.lower().strip(), action)

    def is_action_allowed(self, action: str, details: Optional[Dict[str, Any]] = None) -> bool:
        norm = self.normalize_action(action)
        policy = self.policies.get(norm, (RiskLevel.HIGH, True))
        risk_level, requires_approval = policy
        return not requires_approval

    async def verify_and_authorize(self, action: str, details: Optional[Dict[str, Any]] = None, **kwargs) -> tuple[bool, str]:
        """
        Evaluates risk against security policy.
        If high risk, checks approval cache or awaits user confirmation via callback / Future.
        """
        details = details or {}
        norm_action = self.normalize_action(action)
        policy = self.policies.get(norm_action, (RiskLevel.HIGH, True))
        risk_level, requires_approval = policy

        if not requires_approval:
            return True, "Action permitted automatically by security policy."

        # Check in-memory session whitelist with SHA-256 payload hash (prevents collision across different code payloads)
        import hashlib
        import json
        payload_repr = json.dumps(details, sort_keys=True, default=str)
        payload_hash = hashlib.sha256(payload_repr.encode("utf-8")).hexdigest()[:16]
        approval_key = f"{norm_action}:{payload_hash}"

        if approval_key in self.session_approvals:
            logger.info(f"Action '{norm_action}' (hash: {payload_hash}) auto-approved via session cache.")
            return True, "Action approved via active session permission."

        logger.warning(f"Action '{norm_action}' classified as {risk_level.value}. Requesting user confirmation.")

        # Interactive approval via callback if available
        if self.approval_callback:
            try:
                # Pass session_id if available in kwargs/details
                approved = await self.approval_callback(norm_action, details, **kwargs)
                if approved:
                    self.session_approvals.add(approval_key)
                    return True, "Action approved by user."
                else:
                    return False, f"Action '{norm_action}' was rejected by user."
            except Exception as e:
                logger.error(f"Error during approval callback: {e}")
                return False, f"Approval request failed: {e}"

        return False, f"Action '{norm_action}' requires user approval, but no interactive approval handler is active."

    def register_approval_request(self, request_id: str) -> asyncio.Future:
        """Creates and registers an asyncio Future waiting for UI approval."""
        loop = asyncio.get_event_loop()
        fut = loop.create_future()
        self._pending_requests[request_id] = fut
        return fut

    def resolve_approval_request(self, request_id: str, approved: bool) -> bool:
        """Resolves a pending approval Future when user clicks Approve/Reject in UI."""
        fut = self._pending_requests.pop(request_id, None)
        if fut and not fut.done():
            fut.set_result(approved)
            return True
        return False
