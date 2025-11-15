# Resolve tenant from X-API-Key (hashed in DB). Used by get_current_tenant on all protected routes.
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Optional
from uuid import UUID

from fastapi import Header, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from src.storage.models import Tenant
from src.storage.postgres_client import session_scope


@dataclass
class TenantInfo:
    tenant_id: UUID
    slug: str
    name: str


def hash_api_key(key: str) -> str:
    """SHA-256 hash of normalized key (lowercase, stripped) for lookup."""
    return hashlib.sha256(key.strip().lower().encode()).hexdigest()


async def get_tenant_by_api_key(session: AsyncSession, api_key: str) -> Optional[Tenant]:
    """Look up tenant by API key hash. Returns None if not found."""
    key_hash = hash_api_key(api_key)
    stmt = select(Tenant).where(Tenant.api_key_hash == key_hash)
    result = await session.execute(stmt)
    return result.scalars().first()


async def get_tenant_by_slug(session: AsyncSession, slug: str) -> Optional[Tenant]:
    """Look up tenant by slug."""
    stmt = select(Tenant).where(Tenant.slug == slug)
    result = await session.execute(stmt)
    return result.scalars().first()


async def get_current_tenant(
    request: Request,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
) -> TenantInfo:
    """
    Resolve tenant from X-API-Key header. Use as FastAPI Depends() on protected routes.
    When REQUIRE_AUTH=false and key is missing, use DEFAULT_TENANT_SLUG.
    """
    settings = get_settings()
    if x_api_key and x_api_key.strip():
        async with session_scope() as session:
            tenant = await get_tenant_by_api_key(session, x_api_key)
            if tenant:
                request.state.tenant_id = tenant.tenant_id
                request.state.tenant_slug = tenant.slug
                return TenantInfo(
                    tenant_id=tenant.tenant_id,
                    slug=tenant.slug,
                    name=tenant.name,
                )
        raise HTTPException(status_code=401, detail="Invalid or missing API key")

    if not settings.require_auth:
        async with session_scope() as session:
            tenant = await get_tenant_by_slug(session, settings.default_tenant_slug)
            if tenant:
                request.state.tenant_id = tenant.tenant_id
                request.state.tenant_slug = tenant.slug
                return TenantInfo(
                    tenant_id=tenant.tenant_id,
                    slug=tenant.slug,
                    name=tenant.name,
                )
        raise HTTPException(
            status_code=503,
            detail=f"Default tenant '{settings.default_tenant_slug}' not found. Create it or set REQUIRE_AUTH=true.",
        )

    raise HTTPException(status_code=401, detail="Invalid or missing API key")
