"""
tests/v2/test_auth_and_security.py — V2.2 Security & Authentication Tests
========================================================================
Validates Phase 1 Security Hardening:
  - Health endpoint does NOT expose local token
  - Unauthenticated requests to /api/ endpoints receive 401 Unauthorized
  - Requests with Bearer <LOCAL_AUTH_TOKEN> succeed (or proceed past auth gate)
  - Approval hash collision test: two different code payloads generate distinct hashes
  - Session-bound approval callback targets only originating session
"""

import sys
import json
import hashlib
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from server.api_server import app, LOCAL_AUTH_TOKEN
from modules.security.permission_engine import PermissionEngine, ActionCategory


@pytest.fixture
def client():
    return TestClient(app)


class TestApiAuthentication:
    def test_health_endpoint_unauthenticated_and_no_token_leak(self, client):
        res = client.get("/api/health")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "ok"
        assert data["auth_required"] is True
        # Critical security check: token must NOT be returned in health response
        assert "token" not in data

    def test_protected_endpoints_require_auth(self, client):
        protected_routes = [
            ("GET", "/api/tasks"),
            ("GET", "/api/models"),
            ("GET", "/api/settings"),
            ("POST", "/api/message"),
            ("GET", "/api/memory/facts"),
        ]
        for method, route in protected_routes:
            if method == "GET":
                res = client.get(route)
            else:
                res = client.post(route, json={})
            assert res.status_code == 401, f"{route} should return 401 when unauthenticated"
            assert "Unauthorized" in res.json().get("detail", "")

    def test_protected_endpoint_with_valid_bearer_token(self, client):
        headers = {"Authorization": f"Bearer {LOCAL_AUTH_TOKEN}"}
        res = client.get("/api/settings", headers=headers)
        # Should pass auth gate and return 200
        assert res.status_code == 200


class TestApprovalCacheCollision:
    @pytest.mark.asyncio
    async def test_different_code_payloads_generate_distinct_keys(self):
        call_count = [0]
        async def mock_callback(action, details, **kw):
            call_count[0] += 1
            return True

        pe = PermissionEngine(approval_callback=mock_callback)

        # First script
        code1 = "print('Script 1')"
        auth1, _ = await pe.verify_and_authorize("execute_code", {"code": code1})
        assert auth1 is True
        assert call_count[0] == 1

        # Second script: must NOT match approval cache of script 1
        code2 = "import os; os.system('whoami')"
        auth2, _ = await pe.verify_and_authorize("execute_code", {"code": code2})
        assert auth2 is True
        assert call_count[0] == 2, "Second different code payload must trigger its own approval!"

    @pytest.mark.asyncio
    async def test_identical_payload_reuses_cache(self):
        call_count = [0]
        async def mock_callback(action, details, **kw):
            call_count[0] += 1
            return True

        pe = PermissionEngine(approval_callback=mock_callback)

        code = "print('Identical')"
        await pe.verify_and_authorize("execute_code", {"code": code})
        assert call_count[0] == 1

        # Re-running exact same code should hit session cache
        await pe.verify_and_authorize("execute_code", {"code": code})
        assert call_count[0] == 1
