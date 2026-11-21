"""
tests/v2/test_permissions.py — Permission Engine Tests
=======================================================
Validates PermissionEngine:
  - normalize_action() TOOL_TO_CATEGORY mapping
  - is_action_allowed() policy enforcement
  - verify_and_authorize() with approval callback
  - Session approval caching
  - Unknown actions default to HIGH risk
  - register_approval_request / resolve_approval_request Future resolution
"""

import sys
import asyncio
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from modules.security.permission_engine import (
    PermissionEngine,
    ActionCategory,
    RiskLevel,
    TOOL_TO_CATEGORY,
    DEFAULT_ACTION_POLICIES,
)


# ── Normalization ────────────────────────────────────────────────────

class TestNormalization:
    """Tests for normalize_action() — TOOL_TO_CATEGORY mapping."""

    def test_open_app_maps_to_open_application(self, permission_engine):
        assert permission_engine.normalize_action("open_app") == ActionCategory.OPEN_APPLICATION

    def test_browse_page_maps_to_browse_url(self, permission_engine):
        assert permission_engine.normalize_action("browse_page") == ActionCategory.BROWSE_URL

    def test_execute_code_maps_correctly(self, permission_engine):
        assert permission_engine.normalize_action("execute_code") == ActionCategory.EXECUTE_CODE

    def test_case_insensitive(self, permission_engine):
        assert permission_engine.normalize_action("OPEN_APP") == ActionCategory.OPEN_APPLICATION
        assert permission_engine.normalize_action("  Close_App  ") == ActionCategory.CLOSE_APPLICATION

    def test_unknown_action_passes_through(self, permission_engine):
        assert permission_engine.normalize_action("custom_magic_tool") == "custom_magic_tool"

    def test_all_entries_in_map(self, permission_engine):
        """Every TOOL_TO_CATEGORY entry should normalize correctly."""
        for tool_name, expected_category in TOOL_TO_CATEGORY.items():
            assert permission_engine.normalize_action(tool_name) == expected_category

    def test_skill_calculator_maps_to_calculate(self, permission_engine):
        assert permission_engine.normalize_action("skill_calculator") == ActionCategory.CALCULATE


# ── Policy Enforcement ───────────────────────────────────────────────

class TestPolicyEnforcement:
    """Tests for is_action_allowed() and risk policies."""

    def test_low_risk_actions_allowed_automatically(self, permission_engine):
        low_risk_actions = [
            ActionCategory.SYSTEM_STATUS,
            ActionCategory.TAKE_SCREENSHOT,
            ActionCategory.SEARCH_MEMORY,
            ActionCategory.LIST_WINDOWS,
            ActionCategory.CALCULATE,
        ]
        for action in low_risk_actions:
            assert permission_engine.is_action_allowed(action), f"{action} should be auto-allowed"

    def test_medium_risk_actions_allowed_automatically(self, permission_engine):
        medium_actions = [
            ActionCategory.OPEN_APPLICATION,
            ActionCategory.CLOSE_APPLICATION,
            ActionCategory.BROWSE_URL,
            ActionCategory.FOCUS_WINDOW,
        ]
        for action in medium_actions:
            assert permission_engine.is_action_allowed(action), f"{action} should be auto-allowed"

    def test_high_risk_actions_blocked(self, permission_engine):
        high_risk_actions = [
            ActionCategory.SEND_EMAIL,
            ActionCategory.DELETE_FILE,
            ActionCategory.EXECUTE_CODE,
            ActionCategory.SYSTEM_SHUTDOWN,
        ]
        for action in high_risk_actions:
            assert not permission_engine.is_action_allowed(action), f"{action} should be blocked"

    def test_unknown_action_defaults_to_blocked(self, permission_engine):
        """An unknown action not in DEFAULT_ACTION_POLICIES should default to requiring approval."""
        assert not permission_engine.is_action_allowed("launch_nuclear_missiles")


# ── Verify and Authorize ─────────────────────────────────────────────

class TestVerifyAndAuthorize:
    """Tests for verify_and_authorize() with async approval callbacks."""

    @pytest.mark.asyncio
    async def test_low_risk_auto_approved(self, permission_engine):
        authorized, reason = await permission_engine.verify_and_authorize("system_status")
        assert authorized
        assert "automatically" in reason.lower() or "permitted" in reason.lower()

    @pytest.mark.asyncio
    async def test_high_risk_no_callback_rejected(self):
        """High-risk action with no approval callback should be rejected."""
        pe = PermissionEngine(approval_callback=None)
        authorized, reason = await pe.verify_and_authorize("execute_code", {"code": "print('hi')"})
        assert not authorized
        assert "approval" in reason.lower()

    @pytest.mark.asyncio
    async def test_high_risk_callback_approves(self):
        """High-risk action with callback that returns True → approved."""
        async def auto_approve(action, details):
            return True

        pe = PermissionEngine(approval_callback=auto_approve)
        authorized, reason = await pe.verify_and_authorize("send_email", {"to": "test@test.com"})
        assert authorized
        assert "approved by user" in reason.lower()

    @pytest.mark.asyncio
    async def test_high_risk_callback_rejects(self):
        """High-risk action with callback that returns False → rejected."""
        async def auto_reject(action, details):
            return False

        pe = PermissionEngine(approval_callback=auto_reject)
        authorized, reason = await pe.verify_and_authorize("delete_file", {"path": "/important.txt"})
        assert not authorized
        assert "rejected" in reason.lower()

    @pytest.mark.asyncio
    async def test_session_approval_cache(self):
        """Once approved, same action+target should auto-approve from cache."""
        call_count = [0]

        async def counting_approve(action, details):
            call_count[0] += 1
            return True

        pe = PermissionEngine(approval_callback=counting_approve)
        pe.policies["custom_medium_action"] = (RiskLevel.HIGH, True)

        # First call: callback fires
        auth1, _ = await pe.verify_and_authorize("custom_medium_action", {"target": "custom_target"})
        assert auth1
        assert call_count[0] == 1

        # Second call with same target: should use session cache
        auth2, reason2 = await pe.verify_and_authorize("custom_medium_action", {"target": "custom_target"})
        assert auth2
        assert "session" in reason2.lower()
        assert call_count[0] == 1  # Callback NOT called again

    @pytest.mark.asyncio
    async def test_tool_name_normalized_before_policy_check(self, permission_engine):
        """'open_app' should normalize to 'open_application' and be auto-approved (medium risk)."""
        authorized, reason = await permission_engine.verify_and_authorize("open_app", {"app_name": "notepad"})
        assert authorized


# ── Approval Request Future Resolution ────────────────────────────────

class TestApprovalFutures:
    """Tests for register_approval_request / resolve_approval_request."""

    @pytest.mark.asyncio
    async def test_register_and_resolve_approved(self, permission_engine):
        fut = permission_engine.register_approval_request("req-001")
        assert not fut.done()

        resolved = permission_engine.resolve_approval_request("req-001", True)
        assert resolved
        assert fut.done()
        assert fut.result() == True

    @pytest.mark.asyncio
    async def test_register_and_resolve_rejected(self, permission_engine):
        fut = permission_engine.register_approval_request("req-002")
        resolved = permission_engine.resolve_approval_request("req-002", False)
        assert resolved
        assert fut.result() == False

    @pytest.mark.asyncio
    async def test_resolve_nonexistent_request(self, permission_engine):
        result = permission_engine.resolve_approval_request("req-nonexistent", True)
        assert result == False

    @pytest.mark.asyncio
    async def test_double_resolve_ignored(self, permission_engine):
        fut = permission_engine.register_approval_request("req-003")
        permission_engine.resolve_approval_request("req-003", True)
        # Second resolve should return False (already resolved)
        result = permission_engine.resolve_approval_request("req-003", False)
        assert result == False
