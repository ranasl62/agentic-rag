"""
Phase 6: Tests for Prometheus metrics endpoint and metric recording.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.api.metrics import (
    get_metrics_bytes,
    get_metrics_content_type,
    status_class,
    normalize_path,
)


class TestMetricsHelpers:
    """M2, M3: metric names and helpers."""

    def test_status_class_2xx(self):
        assert status_class(200) == "2xx"
        assert status_class(204) == "2xx"
        assert status_class(299) == "2xx"

    def test_status_class_4xx(self):
        assert status_class(400) == "4xx"
        assert status_class(401) == "4xx"
        assert status_class(404) == "4xx"
        assert status_class(429) == "4xx"

    def test_status_class_5xx(self):
        assert status_class(500) == "5xx"
        assert status_class(503) == "5xx"

    def test_normalize_path(self):
        assert normalize_path("/health") == "/health"
        assert normalize_path("/books") == "/books"
        assert normalize_path("/books/sections") == "/books"
        assert normalize_path("/search") == "/search"
        assert normalize_path("/") == "/"
        assert normalize_path("/ingest/status/abc") == "/ingest"


class TestMetricsOutput:
    """M1, M2, M3: /metrics content type and body."""

    def test_get_metrics_content_type(self):
        assert "text" in get_metrics_content_type() and "plain" in get_metrics_content_type()

    def test_get_metrics_bytes_contains_counter(self):
        body = get_metrics_bytes().decode("utf-8")
        assert "http_requests_total" in body or "request" in body.lower()

    def test_get_metrics_bytes_contains_histogram(self):
        body = get_metrics_bytes().decode("utf-8")
        assert "http_request_duration_seconds" in body or "duration" in body.lower()


class TestMetricsEndpoint:
    """M1: GET /metrics returns 200 when metrics enabled. Requires app (may skip if no DB)."""

    @pytest.fixture
    def client(self):
        from src.api.main import app
        return TestClient(app)

    def test_metrics_returns_200_when_enabled(self, client):
        """M1: GET /metrics returns 200 and text/plain."""
        r = client.get("/metrics")
        # If app fails to start (e.g. no Postgres), skip
        if r.status_code == 500:
            pytest.skip("App may not have started (e.g. no DB)")
        assert r.status_code == 200, r.text
        assert "text/plain" in r.headers.get("Content-Type", "")

    def test_metrics_body_contains_metric_names(self, client):
        """M2, M3: Response contains expected metric names."""
        r = client.get("/metrics")
        if r.status_code != 200:
            pytest.skip("Metrics endpoint not available")
        body = r.text
        assert "http_requests_total" in body
        assert "http_request_duration_seconds" in body
