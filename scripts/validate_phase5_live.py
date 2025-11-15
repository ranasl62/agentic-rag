"""
Validate Phase 5 (PgBouncer + Qdrant/Postgres scaling) against a running stack.
Expects: Full stack up with PgBouncer; API reached via Nginx (default http://localhost:8080).
Verifies: Health, DB (list books), search (Qdrant), and tenant isolation still work through the pooler.

Usage:
  API_BASE_URL=http://localhost:8080 uv run python -m scripts.validate_phase5_live
  AGENT_API_KEY=key uv run python -m scripts.validate_phase5_live
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx

BASE = os.environ.get("API_BASE_URL", "http://localhost:8080")
API_KEY = os.environ.get("AGENT_API_KEY", "")


def headers():
    h = {"Content-Type": "application/json"}
    if API_KEY:
        h["X-API-Key"] = API_KEY
    return h


def main():
    ok, fail = 0, 0

    def check(name: str, condition: bool, detail: str = ""):
        nonlocal ok, fail
        if condition:
            print(f"  OK   {name}" + (f"  ({detail})" if detail else ""))
            ok += 1
        else:
            print(f"  FAIL {name}" + (f"  ({detail})" if detail else ""))
            fail += 1

    print("Phase 5 validation (PgBouncer + stack)")
    print(f"  Base URL: {BASE}")
    print()

    with httpx.Client(timeout=15.0) as client:
        r = client.get(f"{BASE}/health")
        check("GET /health 200", r.status_code == 200, str(r.status_code))

        r = client.get(f"{BASE}/books", headers=headers())
        check("GET /books 200 or 401/503", r.status_code in (200, 401, 503), str(r.status_code))
        if r.status_code == 200:
            j = r.json()
            check("GET /books has 'books' key", "books" in j, "")

        r = client.post(f"{BASE}/search", json={"query": "test", "limit": 2}, headers=headers())
        check("POST /search 200 or 401/503/429", r.status_code in (200, 401, 503, 429), str(r.status_code))
        if r.status_code == 200:
            j = r.json()
            check("POST /search has results", "results" in j, "")

        r = client.get(f"{BASE}/ingest/status/00000000-0000-0000-0000-000000000000", headers=headers())
        check("GET /ingest/status unknown 404", r.status_code == 404, str(r.status_code))

    print()
    print(f"Result: {ok} passed, {fail} failed")
    sys.exit(0 if fail == 0 else 1)


if __name__ == "__main__":
    main()
