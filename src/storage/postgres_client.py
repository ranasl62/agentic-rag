"""
Async PostgreSQL client and session management for metadata storage.
Engine is created lazily on first use so Docker env is fully available at startup.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    AsyncEngine,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy import select

from config import get_settings
from src.storage.models import Base, Tenant

_engine: AsyncEngine | None = None
_async_session_factory: async_sessionmaker[AsyncSession] | None = None


def _get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(
            settings.postgres_url,
            echo=False,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
        )
    return _engine


def _get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _async_session_factory
    if _async_session_factory is None:
        _async_session_factory = async_sessionmaker(
            _get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )
    return _async_session_factory


class _LazySessionFactory:
    """Lazy wrapper so session factory is created on first use (after Docker env is ready)."""

    def __call__(self):
        return _get_session_factory()()


AsyncSessionLocal = _LazySessionFactory()


async def init_db() -> None:
    """Create all tables. Call once at startup."""
    engine = _get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def ensure_default_tenant() -> None:
    """Ensure a default tenant exists (for REQUIRE_AUTH=false and for backfill). Idempotent."""
    async with _get_session_factory()() as session:
        stmt = select(Tenant).where(Tenant.slug == get_settings().default_tenant_slug)
        result = await session.execute(stmt)
        if result.scalars().first() is None:
            session.add(
                Tenant(
                    name="Default Tenant",
                    slug=get_settings().default_tenant_slug,
                    api_key_hash=None,
                )
            )
            await session.commit()


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency: yield an async session for the request lifecycle."""
    async with _get_session_factory()() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@asynccontextmanager
async def session_scope() -> AsyncGenerator[AsyncSession, None]:
    """Programmatic session scope for use outside FastAPI dependencies."""
    async with _get_session_factory()() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
