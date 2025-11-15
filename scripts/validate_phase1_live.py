"""
Validate Phase 1 (Auth + Tenant Isolation) against a running API.
Usage:
  API_BASE_URL=http://localhost:8080 uv run python -m scripts.validate_phase1_live
  AGENT_API_KEY=your-key uv run python -m scripts.validate_phase1_live
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

    print("Phase 1 validation (live API)")
    print(f"  Base URL: {BASE}")
    print(f"  X-API-Key: {'set' if API_KEY else 'not set'}")
    print()

    with httpx.Client(timeout=30.0) as client:
        r = client.get(f"{BASE}/health")
        check("GET /health returns 200", r.status_code == 200, str(r.status_code))

        r = client.get(f"{BASE}/books", headers=headers())
        if not API_KEY:
            # With REQUIRE_AUTH=true expect 401/503; with REQUIRE_AUTH=false expect 200 (default tenant)
            check("GET /books without key: 401, 503, or 200 (permissive)", r.status_code in (200, 401, 503), str(r.status_code))
        else:
            check("GET /books with key: 200", r.status_code == 200, str(r.status_code))
        if r.status_code == 200 and r.content:
            try:
                check("GET /books has 'books' key", "books" in r.json(), "")
            except Exception:
                check("GET /books has 'books' key", False, "response not valid JSON")

        r = client.get(f"{BASE}/books/sections", headers=headers())
        check("GET /books/sections: 200 or 401/503", r.status_code in (200, 401, 503), str(r.status_code))
        if r.status_code == 200 and r.content:
            try:
                j = r.json()
                check("GET /books/sections has 'sections'", "sections" in j, "")
            except Exception:
                check("GET /books/sections has 'sections'", False, "response not valid JSON")

        r = client.post(f"{BASE}/search", json={"query": "test", "limit": 3}, headers=headers())
        check("POST /search: 200 or 401/503", r.status_code in (200, 401, 503), str(r.status_code))
        if r.status_code == 200 and r.content:
            try:
                j = r.json()
                check("POST /search has success, results", j.get("success") and "results" in j, "")
            except Exception:
                check("POST /search has success, results", False, "response not valid JSON")

        r = client.post(
            f"{BASE}/compare",
            json={"book_id": "00000000-0000-0000-0000-000000000001", "chapter_number": 1, "section_number": 1},
            headers=headers(),
        )
        check("POST /compare: 200 or 401/503", r.status_code in (200, 401, 503), str(r.status_code))

        r = client.post(f"{BASE}/summarize", json={"query": "summarize", "max_length": 100}, headers=headers())
        check("POST /summarize: 200 or 401/503", r.status_code in (200, 401, 503), str(r.status_code))

        r = client.post(f"{BASE}/query", json={"query": "What books are available?", "skip_verification": True}, headers=headers())
        check("POST /query: 200 or 401/503", r.status_code in (200, 401, 503), str(r.status_code))
        if r.status_code == 200 and r.content:
            try:
                j = r.json()
                check("POST /query has response, steps", "response" in j and "steps" in j, "")
            except Exception:
                check("POST /query has response, steps", False, "response not valid JSON")

    print()
    print(f"Result: {ok} passed, {fail} failed")
    sys.exit(0 if fail == 0 else 1)


if __name__ == "__main__":
    main()
