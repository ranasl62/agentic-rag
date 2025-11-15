"""
Backfill tenant_id for existing databases that have books without tenant_id.
Run once after Phase 1 schema: python -m scripts.backfill_tenant

Creates tenants table if missing, adds books.tenant_id, inserts default tenant,
assigns all existing books to default tenant.
"""
import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from config import get_settings


def main():
    from sqlalchemy import create_engine

    settings = get_settings()
    url = settings.postgres_url_sync
    engine = create_engine(url)

    with engine.connect() as conn:
        # Check if tenants table exists
        r = conn.execute(text(
            "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'tenants')"
        ))
        tenants_exists = r.scalar()
        if not tenants_exists:
            conn.execute(text("""
                CREATE TABLE tenants (
                    tenant_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    name TEXT NOT NULL,
                    slug TEXT NOT NULL,
                    api_key_hash TEXT,
                    created_at TIMESTAMP DEFAULT (NOW() AT TIME ZONE 'utc'),
                    metadata JSONB
                );
                CREATE UNIQUE INDEX uq_tenants_slug ON tenants(slug);
            """))
            conn.commit()
            print("Created tenants table.")
        else:
            print("Tenants table already exists.")

        # Check if books.tenant_id exists
        r = conn.execute(text("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'books' AND column_name = 'tenant_id'
            )
        """))
        has_tenant_id = r.scalar()
        if has_tenant_id:
            print("books.tenant_id already exists. Nothing to backfill.")
            return

        default_slug = settings.default_tenant_slug
        # Ensure default tenant exists
        r = conn.execute(text("SELECT tenant_id FROM tenants WHERE slug = :slug"), {"slug": default_slug})
        row = r.fetchone()
        if not row:
            tenant_id = str(uuid.uuid4())
            conn.execute(
                text("INSERT INTO tenants (tenant_id, name, slug) VALUES (:id, 'Default Tenant', :slug)"),
                {"id": tenant_id, "slug": default_slug}
            )
            conn.commit()
            print(f"Inserted default tenant {default_slug} ({tenant_id}).")
        else:
            tenant_id = str(row[0])

        # Add column as nullable first
        conn.execute(text("ALTER TABLE books ADD COLUMN IF NOT EXISTS tenant_id UUID REFERENCES tenants(tenant_id)"))
        conn.commit()
        # Assign existing books to default tenant
        conn.execute(text("UPDATE books SET tenant_id = :tid WHERE tenant_id IS NULL"), {"tid": tenant_id})
        conn.commit()
        # Make NOT NULL
        conn.execute(text("ALTER TABLE books ALTER COLUMN tenant_id SET NOT NULL"))
        conn.commit()
        # Add unique constraint name change if needed: uq_books_title_author may need to be dropped and recreated as uq_books_title_author_tenant
        # For simplicity we don't alter unique constraint here; the app uses uq_books_title_author_tenant for new deployments.
        print("Backfill complete: books.tenant_id set to default tenant.")
    print("Done.")


if __name__ == "__main__":
    main()
