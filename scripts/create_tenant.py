"""
Create a tenant and generate an API key.
Requires: tenants table to exist (run the API once or scripts/backfill_tenant.py first).

Usage:
  uv run python -m scripts.create_tenant "Acme Dealers" acme-dealers
  uv run python -m scripts.create_tenant "My Brand" my-brand

Outputs the API key once; store it securely (only the hash is stored in the DB).
"""
from __future__ import annotations

import asyncio
import hashlib
import secrets
import sys
from uuid import uuid4

# Ensure project root on path
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from config import get_settings


def hash_api_key(key: str) -> str:
    return hashlib.sha256(key.strip().lower().encode()).hexdigest()


async def _run():
    if len(sys.argv) < 3:
        print("Usage: python -m scripts.create_tenant <name> <slug>")
        print("  e.g. python -m scripts.create_tenant 'Acme Dealers' acme-dealers")
        sys.exit(1)
    name = sys.argv[1].strip()
    slug = sys.argv[2].strip().lower().replace(" ", "-")
    if not name or not slug:
        print("Name and slug are required.")
        sys.exit(1)

    settings = get_settings()
    engine = create_async_engine(settings.postgres_url)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    api_key = secrets.token_urlsafe(32)
    key_hash = hash_api_key(api_key)
    tenant_id = str(uuid4())

    async with async_session() as session:
        r = await session.execute(text("SELECT 1 FROM tenants WHERE slug = :slug"), {"slug": slug})
        if r.scalar() is not None:
            print(f"Tenant with slug '{slug}' already exists. Choose a different slug.")
            sys.exit(1)
        await session.execute(
            text("""
                INSERT INTO tenants (tenant_id, name, slug, api_key_hash)
                VALUES (:id, :name, :slug, :api_key_hash)
            """),
            {"id": tenant_id, "name": name, "slug": slug, "api_key_hash": key_hash},
        )
        await session.commit()

    await engine.dispose()
    print(f"Created tenant: {name} (slug={slug}, tenant_id={tenant_id})")
    print("API key (store securely; shown once):")
    print(api_key)
    print("\nUse in requests: Header X-API-Key: <key above>")


def main():
    asyncio.run(_run())


if __name__ == "__main__":
    main()
