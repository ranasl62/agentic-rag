"""
Phase 2: Rate limiting and cache tests.
Run with: uv run python -m pytest tests/test_phase2_rate_limit_cache.py -v
"""
from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from src.api.auth import TenantInfo, get_current_tenant
from src.api.cache import query_cache_key, search_cache_key
from src.api.main import app
from src.api.rate_limit import ENDPOINT_SEARCH, check_rate_limit, RateLimitExceeded

FAKE_TENANT_ID = uuid.UUID("a0000000-0000-0000-0000-000000000001")
FAKE_TENANT = TenantInfo(tenant_id=FAKE_TENANT_ID, slug="test-tenant", name="Test Tenant")


async def override_get_current_tenant(request=None, x_api_key=None):
    return FAKE_TENANT


@pytest.fixture
def client():
    app.dependency_overrides[get_current_tenant] = override_get_current_tenant
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


class TestCacheKeys:
    def test_search_cache_key_deterministic(self):
        key1 = search_cache_key(FAKE_TENANT_ID, "q", None, None, 10, False)
        key2 = search_cache_key(FAKE_TENANT_ID, "q", None, None, 10, False)
        assert key1 == key2

    def test_search_cache_key_different_query(self):
        key1 = search_cache_key(FAKE_TENANT_ID, "q1", None, None, 10, False)
        key2 = search_cache_key(FAKE_TENANT_ID, "q2", None, None, 10, False)
        assert key1 != key2

    def test_query_cache_key_deterministic(self):
        key1 = query_cache_key(FAKE_TENANT_ID, "what books?")
        key2 = query_cache_key(FAKE_TENANT_ID, "what books?")
        assert key1 == key2


class TestRateLimitDisabled:
    """When RATE_LIMIT_ENABLED=false, check_rate_limit should not raise."""

    @pytest.mark.asyncio
    async def test_no_raise_when_disabled(self):
        with patch("src.api.rate_limit.get_settings") as m:
            m.return_value.rate_limit_enabled = False
            await check_rate_limit(ENDPOINT_SEARCH, FAKE_TENANT, None)


class TestRateLimitExceeded:
    def test_response_has_429_and_retry_after(self):
        from src.api.rate_limit import rate_limit_response
        exc = RateLimitExceeded(retry_after_seconds=60)
        resp = rate_limit_response(exc)
        assert resp.status_code == 429
        assert resp.headers.get("Retry-After") == "60"


@pytest.mark.skip(reason="Requires Postgres/Redis; use scripts/validate_phase2_live.py against running API")
class TestPhase2EndpointsWithRateLimit:
    """Endpoints still return 200 when rate limit not exceeded (limit is high by default)."""

    def test_search_returns_200(self, client):
        r = client.post("/search", json={"query": "test", "limit": 5})
        assert r.status_code == 200
        assert "results" in r.json()

    def test_query_returns_200(self, client):
        r = client.post("/query", json={"query": "What books?", "skip_verification": True})
        assert r.status_code == 200
        assert "response" in r.json()
