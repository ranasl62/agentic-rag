"""
Phase 3: Async ingestion tests (job status, 202 response shape).
Run: uv run python -m pytest tests/test_phase3_async_ingest.py -v
"""
from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from src.api.main import app
from src.api.auth import TenantInfo, get_current_tenant
from src.worker.celery_app import get_job_status, set_job_status

FAKE_TENANT = TenantInfo(
    tenant_id="a0000000-0000-0000-0000-000000000001",
    slug="test",
    name="Test",
)


async def override_tenant(request=None, x_api_key=None):
    return FAKE_TENANT


@pytest.fixture
def client():
    app.dependency_overrides[get_current_tenant] = override_tenant
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


class TestJobStatus:
    """Job status helpers (no Celery broker needed)."""

    def test_set_and_get_job_status(self):
        set_job_status("test-job-1", "pending", created_at="2025-01-01T00:00:00Z")
        data = get_job_status("test-job-1")
        assert data is not None
        assert data["job_id"] == "test-job-1"
        assert data["status"] == "pending"
        assert "created_at" in data

    def test_get_missing_job_returns_none(self):
        data = get_job_status("nonexistent-job-id-12345")
        assert data is None


@pytest.mark.skip(reason="Requires Postgres (app lifespan); use scripts/validate_phase3_live.py against running API")
class TestIngestStatusEndpoint:
    """GET /ingest/status/{job_id} (no worker needed)."""

    def test_status_404_when_job_missing(self, client):
        r = client.get("/ingest/status/nonexistent-uuid")
        assert r.status_code == 404

    def test_status_200_when_job_exists(self, client):
        set_job_status("existing-job", "completed", result={"sections_count": 5})
        r = client.get("/ingest/status/existing-job")
        assert r.status_code == 200
        data = r.json()
        assert data["job_id"] == "existing-job"
        assert data["status"] == "completed"
        assert data.get("result", {}).get("sections_count") == 5
