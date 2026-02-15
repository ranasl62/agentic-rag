"""
Create a tenant and generate an API key.
Requires: tenants table to exist (run the API once or scripts/backfill_tenant.py first).

Usage:
  uv run python -m scripts.create_tenant "Acme Dealers" acme-dealers
  uv run python -m scripts.create_tenant "My Brand" my-brand

When Postgres runs in Docker, from the host use port 5433 (published port):
  POSTGRES_PORT=5433 uv run python -m scripts.create_tenant "My Tenant" my-tenant
Or run inside the stack (uses same env as API):
  docker compose run --rm api-service python -m scripts.create_tenant "My Tenant" my-tenant

Outputs the API key once; store it securely (only the hash is stored in the DB).
"""
from __future__ import annotations

import asyncio
import hashlib
import secrets
import sys
from datetime import datetime
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
        now = datetime.utcnow()
        await session.execute(
            text("""
                INSERT INTO tenants (tenant_id, name, slug, api_key_hash, created_at)
                VALUES (:id, :name, :slug, :api_key_hash, :created_at)
            """),
            {"id": tenant_id, "name": name, "slug": slug, "api_key_hash": key_hash, "created_at": now},
        )
        await session.commit()

    await engine.dispose()
    print(f"Created tenant: {name} (slug={slug}, tenant_id={tenant_id})")
    print("API key (store securely; shown once):")
    print(api_key)
    print("\nUse in requests: Header X-API-Key: <key above>")


def main():
    try:
        asyncio.run(_run())
    except Exception as e:
        err = str(e).lower()
        if "password" in err or "authentication" in err:
            print("Database authentication failed. Tips:", file=sys.stderr)
            print("  - Postgres in Docker is on port 5433 from the host. Run:", file=sys.stderr)
            print("    POSTGRES_PORT=5433 uv run python -m scripts.create_tenant \"My Tenant\" my-tenant", file=sys.stderr)
            print("  - Or run inside Docker (uses API env):", file=sys.stderr)
            print("    docker compose run --rm api-service python -m scripts.create_tenant \"My Tenant\" my-tenant", file=sys.stderr)
            print("  - Ensure POSTGRES_PASSWORD in .env matches the password used when the Postgres container was first started.", file=sys.stderr)
        raise


if __name__ == "__main__":
    main()
