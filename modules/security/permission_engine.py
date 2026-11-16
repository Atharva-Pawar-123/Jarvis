"""
modules/security/permission_engine.py — JARVIS Central Action-Risk Permission Gate
================================================================================
Enforces the principle of least privilege and human-in-the-loop control for all
JARVIS actions. The LLM is never the authority deciding whether an action is allowed.
"""

import enum
import logging
import asyncio
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
    BROWSE_URL = "browse_url"

    # Low / Automatic
    ANSWER_QUESTION = "answer_question"
    SEARCH_WEB = "search_web"
    READ_FILE = "read_file"
    DRAFT_EMAIL = "draft_email"
    DRAFT_WHATSAPP = "draft_whatsapp"
    SYSTEM_STATUS = "system_status"
    LIST_FILES = "list_files"


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

    # Medium / Scoped
    ActionCategory.WRITE_FILE: (RiskLevel.MEDIUM, False),
    ActionCategory.OPEN_APPLICATION: (RiskLevel.MEDIUM, False),
    ActionCategory.BROWSE_URL: (RiskLevel.MEDIUM, False),

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
        # approval_callback: async callable(action: str, details: dict) -> bool
        self.approval_callback = approval_callback
        # In-session temporary whitelist for approved actions: set of action keys
        self.session_approvals: set[str] = set()

    def set_approval_callback(self, callback):
        self.approval_callback = callback

    def is_action_allowed(self, action: str, details: Optional[Dict[str, Any]] = None) -> bool:
        """Synchronously check if action is automatic (returns True) or requires gate (returns False)."""
        policy = self.policies.get(action, (RiskLevel.HIGH, True))
        risk_level, requires_approval = policy
        if not requires_approval:
            return True
        return False

    async def verify_and_authorize(self, action: str, details: Optional[Dict[str, Any]] = None) -> tuple[bool, str]:
        """
        Evaluates risk. If high risk, triggers human-in-the-loop approval.
        Returns: (authorized: bool, reason: str)
        """
        details = details or {}
        policy = self.policies.get(action, (RiskLevel.HIGH, True))
        risk_level, requires_approval = policy

        if not requires_approval:
            return True, "Action permitted automatically by security policy."

        # Check if already approved for this specific payload/session
        approval_key = f"{action}:{str(details.get('target', ''))}"
        if approval_key in self.session_approvals:
            logger.info(f"Action '{action}' auto-approved via session cache.")
            return True, "Action approved via active session permission."

        logger.warning(f"Action '{action}' classified as {risk_level.value}. Requesting user confirmation.")

        if self.approval_callback:
            try:
                approved = await self.approval_callback(action, details)
                if approved:
                    self.session_approvals.add(approval_key)
                    return True, "Action approved by user."
                else:
                    return False, f"Action '{action}' was rejected by user."
            except Exception as e:
                logger.error(f"Error during approval callback: {e}")
                return False, f"Approval request failed: {e}"

        # If no UI callback is attached, fail safe
        return False, f"Action '{action}' requires user approval, but no interactive approval handler is active."
