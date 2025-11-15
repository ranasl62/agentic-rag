"""
Phase 2: Rate limiting per tenant (and optional per IP) via Redis.
Runs after auth; returns 429 with Retry-After when limit exceeded.
"""
from __future__ import annotations

import time
from typing import Optional

from fastapi import Depends, Request
from fastapi.responses import JSONResponse

from config import get_settings
from src.api.auth import TenantInfo, get_current_tenant
from src.storage.redis_client import get_redis_client

# Endpoint names used for Redis keys and config lookup
ENDPOINT_SEARCH = "search"
ENDPOINT_QUERY = "query"
ENDPOINT_UPLOAD = "upload"
ENDPOINT_COMPARE = "compare"
ENDPOINT_SUMMARIZE = "summarize"
ENDPOINT_LIST = "list"

LIMIT_CONFIG = {
    ENDPOINT_SEARCH: "rate_limit_search_per_min",
    ENDPOINT_QUERY: "rate_limit_query_per_min",
    ENDPOINT_UPLOAD: "rate_limit_upload_per_min",
    ENDPOINT_COMPARE: "rate_limit_compare_per_min",
    ENDPOINT_SUMMARIZE: "rate_limit_summarize_per_min",
    ENDPOINT_LIST: "rate_limit_list_per_min",
}


async def check_rate_limit(
    endpoint: str,
    tenant: TenantInfo,
    request: Optional[Request] = None,
) -> None:
    """
    Check rate limit for this endpoint and tenant. Optionally check per-IP.
    Raises (via JSONResponse) 429 with Retry-After if over limit.
    """
    settings = get_settings()
    if not settings.rate_limit_enabled:
        return

    limit_attr = LIMIT_CONFIG.get(endpoint)
    if not limit_attr:
        return
    limit = getattr(settings, limit_attr, 0)
    if limit <= 0:
        return

    redis = get_redis_client()
    minute_slot = int(time.time() // 60)
    tenant_key = f"rl:{endpoint}:{tenant.tenant_id}:{minute_slot}"

    n = await redis.incr(tenant_key)
    if n == 1:
        await redis.expire(tenant_key, 61)

    if n > limit:
        raise RateLimitExceeded(retry_after_seconds=60)

    # Optional per-IP limit
    ip_limit = getattr(settings, "rate_limit_ip_per_min", 0) or 0
    if ip_limit > 0 and request:
        client_ip = request.client.host if request.client else "unknown"
        ip_key = f"rl:ip:{client_ip}:{minute_slot}"
        ip_n = await redis.incr(ip_key)
        if ip_n == 1:
            await redis.expire(ip_key, 61)
        if ip_n > ip_limit:
            raise RateLimitExceeded(retry_after_seconds=60)


class RateLimitExceeded(Exception):
    def __init__(self, retry_after_seconds: int = 60):
        self.retry_after_seconds = retry_after_seconds


def rate_limit_response(exc: RateLimitExceeded) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={"detail": "Rate limit exceeded. Try again later."},
        headers={"Retry-After": str(exc.retry_after_seconds)},
    )


def rate_limit_dependency(endpoint: str):
    """Returns a FastAPI dependency that checks rate limit for the given endpoint. Depends on get_current_tenant."""

    async def _check(
        request: Request,
        tenant: TenantInfo = Depends(get_current_tenant),
    ):
        await check_rate_limit(endpoint, tenant, request)

    return _check
