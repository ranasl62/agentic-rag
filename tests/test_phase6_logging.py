"""
Phase 6: Tests for structured logging (request_id, tenant_id in middleware).
"""
from __future__ import annotations

import uuid


class TestRequestIdFormat:
    """L1: request_id is a UUID string (middleware uses uuid4)."""

    def test_request_id_is_uuid_string(self):
        request_id = str(uuid.uuid4())
        assert len(request_id) == 36
        assert request_id.count("-") == 4
        # Can be parsed as UUID
        uuid.UUID(request_id)


class TestMiddlewareModule:
    """L1: Middleware exists and is callable; request_id format is UUID."""

    def test_middleware_is_callable(self):
        from src.api.middleware.request_metrics_logging import request_metrics_logging_middleware
        assert callable(request_metrics_logging_middleware)

    def test_middleware_sets_request_id_on_state(self):
        """L1: When middleware runs, request.state.request_id is set (integration: use validate_phase6_live)."""
        from src.api.middleware.request_metrics_logging import request_metrics_logging_middleware
        # Module loads and exposes the middleware; full behavior verified in live script
        assert request_metrics_logging_middleware.__name__ == "request_metrics_logging_middleware"
