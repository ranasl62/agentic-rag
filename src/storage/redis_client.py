"""
Redis client for caching and optional job/state storage.
"""
from __future__ import annotations

import json
from typing import Any, Optional

import redis.asyncio as redis
from redis.asyncio import Redis

from config import get_settings

_default_client: Optional[Redis] = None


class RedisClient:
    """Async Redis wrapper for cache and agent state."""

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        db: Optional[int] = None,
    ) -> None:
        s = get_settings()
        self._host = host or s.redis_host
        self._port = port or s.redis_port
        self._db = db if db is not None else s.redis_db
        self._client: Optional[Redis] = None

    @property
    def client(self) -> Redis:
        if self._client is None:
            self._client = redis.Redis(
                host=self._host,
                port=self._port,
                db=self._db,
                decode_responses=True,
            )
        return self._client

    async def get(self, key: str) -> Optional[str]:
        return await self.client.get(key)

    async def set(
        self,
        key: str,
        value: str,
        ttl_seconds: Optional[int] = None,
    ) -> None:
        if ttl_seconds is not None:
            await self.client.setex(key, ttl_seconds, value)
        else:
            await self.client.set(key, value)

    async def get_json(self, key: str) -> Optional[Any]:
        raw = await self.get(key)
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None

    async def set_json(
        self,
        key: str,
        value: Any,
        ttl_seconds: Optional[int] = None,
    ) -> None:
        await self.set(key, json.dumps(value), ttl_seconds=ttl_seconds)

    async def delete(self, key: str) -> None:
        await self.client.delete(key)

    async def incr(self, key: str) -> int:
        """Increment key; return new value. Use for rate limiting."""
        return await self.client.incr(key)

    async def expire(self, key: str, seconds: int) -> None:
        await self.client.expire(key, seconds)

    async def close(self) -> None:
        if self._client:
            await self._client.close()
            self._client = None


_redis_client: Optional[RedisClient] = None


def get_redis_client() -> RedisClient:
    global _redis_client
    if _redis_client is None:
        _redis_client = RedisClient()
    return _redis_client
