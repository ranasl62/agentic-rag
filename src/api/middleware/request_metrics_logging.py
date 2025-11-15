"""
Phase 6: Middleware for Prometheus metrics and structured request logging.
Sets request_id, records request count + duration, logs JSON with request_id, tenant_id, endpoint, status, duration.
"""
from __future__ import annotations

import time
import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from config import get_settings
from src.api.metrics import (
    HTTP_REQUEST_DURATION_SECONDS,
    HTTP_REQUESTS_TOTAL,
    normalize_path,
    status_class,
)


def _get_tenant_id(request: Request) -> str | None:
    """Get tenant_id from request.state if set (after auth)."""
    return getattr(request.state, "tenant_id", None)


async def request_metrics_logging_middleware(request: Request, call_next) -> Response:
    """Record metrics and log one structured line per request."""
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    start = time.perf_counter()

    response = await call_next(request)

    duration_sec = time.perf_counter() - start
    duration_ms = round(duration_sec * 1000)
    status = response.status_code
    method = request.method
    path = request.url.path
    endpoint = normalize_path(path)

    settings = get_settings()
    if getattr(settings, "metrics_enabled", True):
        HTTP_REQUESTS_TOTAL.labels(
            method=method,
            endpoint=endpoint,
            status_class=status_class(status),
        ).inc()
        HTTP_REQUEST_DURATION_SECONDS.labels(
            method=method,
            endpoint=endpoint,
        ).observe(duration_sec)

    tenant_id = _get_tenant_id(request)
    structlog.get_logger().info(
        "request",
        request_id=request_id,
        tenant_id=str(tenant_id) if tenant_id else None,
        method=method,
        path=path,
        endpoint=endpoint,
        status_code=status,
        duration_ms=duration_ms,
    )
    return response
