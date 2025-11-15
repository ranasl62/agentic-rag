"""
Phase 5: PgBouncer and config tests.
Verifies that Postgres URL is built from env (so PgBouncer host/port can be used).
"""
from __future__ import annotations

import os
import pytest


def test_postgres_url_uses_env_host_port(monkeypatch):
    """When POSTGRES_HOST and POSTGRES_PORT are set, postgres_url includes them."""
    monkeypatch.setenv("POSTGRES_HOST", "pgbouncer")
    monkeypatch.setenv("POSTGRES_PORT", "6432")
    monkeypatch.setenv("POSTGRES_USER", "agentic_rag")
    monkeypatch.setenv("POSTGRES_PASSWORD", "secret")
    monkeypatch.setenv("POSTGRES_DB", "agentic_rag")
    # Clear lru_cache so get_settings picks up new env
    from config import get_settings
    get_settings.cache_clear()
    try:
        s = get_settings()
        url = s.postgres_url
        assert "pgbouncer" in url
        assert "6432" in url
        assert "agentic_rag" in url
    finally:
        get_settings.cache_clear()


def test_postgres_url_sync_uses_same_host_port(monkeypatch):
    """postgres_url_sync uses same host/port as postgres_url (for scripts using pooler)."""
    monkeypatch.setenv("POSTGRES_HOST", "pgbouncer")
    monkeypatch.setenv("POSTGRES_PORT", "6432")
    monkeypatch.setenv("POSTGRES_USER", "u")
    monkeypatch.setenv("POSTGRES_PASSWORD", "p")
    monkeypatch.setenv("POSTGRES_DB", "db")
    from config import get_settings
    get_settings.cache_clear()
    try:
        s = get_settings()
        sync_url = s.postgres_url_sync
        assert "pgbouncer" in sync_url and "6432" in sync_url
    finally:
        get_settings.cache_clear()
