"""
Phase 2: Redis cache for search and query results. Tenant-scoped keys, configurable TTL.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, Optional
from uuid import UUID

from config import get_settings
from src.storage.redis_client import get_redis_client


def _cache_key(prefix: str, tenant_id: UUID, *parts: str) -> str:
    raw = "|".join(str(p) for p in parts)
    h = hashlib.sha256(raw.encode()).hexdigest()[:32]
    return f"{prefix}:{tenant_id}:{h}"


def search_cache_key(
    tenant_id: UUID,
    query: str,
    book_id: Optional[str],
    edition_id: Optional[str],
    limit: int,
    generate_answer: bool = False,
) -> str:
    return _cache_key(
        "search", tenant_id, query or "", book_id or "", edition_id or "", str(limit), str(generate_answer)
    )


def query_cache_key(tenant_id: UUID, query: str) -> str:
    return _cache_key("query", tenant_id, query or "")


async def get_search_cached(
    tenant_id: UUID,
    query: str,
    book_id: Optional[str],
    edition_id: Optional[str],
    limit: int,
    generate_answer: bool = False,
) -> Optional[Dict[str, Any]]:
    if not get_settings().cache_enabled or get_settings().cache_search_ttl_seconds <= 0:
        return None
    key = search_cache_key(tenant_id, query, book_id, edition_id, limit, generate_answer)
    return await get_redis_client().get_json(key)


async def set_search_cached(
    tenant_id: UUID,
    query: str,
    book_id: Optional[str],
    edition_id: Optional[str],
    limit: int,
    value: Dict[str, Any],
    generate_answer: bool = False,
) -> None:
    if not get_settings().cache_enabled or get_settings().cache_search_ttl_seconds <= 0:
        return
    key = search_cache_key(tenant_id, query, book_id, edition_id, limit, generate_answer)
    await get_redis_client().set_json(key, value, ttl_seconds=get_settings().cache_search_ttl_seconds)


async def get_query_cached(tenant_id: UUID, query: str) -> Optional[Dict[str, Any]]:
    if not get_settings().cache_enabled or get_settings().cache_query_ttl_seconds <= 0:
        return None
    key = query_cache_key(tenant_id, query)
    return await get_redis_client().get_json(key)


async def set_query_cached(tenant_id: UUID, query: str, value: Dict[str, Any]) -> None:
    if not get_settings().cache_enabled or get_settings().cache_query_ttl_seconds <= 0:
        return
    key = query_cache_key(tenant_id, query)
    await get_redis_client().set_json(key, value, ttl_seconds=get_settings().cache_query_ttl_seconds)
