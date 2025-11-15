"""
Validate Phase 2 (Rate limiting + cache) against a running API.
Usage:
  API_BASE_URL=http://localhost:8080 uv run python -m scripts.validate_phase2_live
  AGENT_API_KEY=key uv run python -m scripts.validate_phase2_live
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

    print("Phase 2 validation (rate limit + cache)")
    print(f"  Base URL: {BASE}")
    print()

    with httpx.Client(timeout=30.0) as client:
        # Search: 200 and has results/citations (cache may serve)
        r = client.post(f"{BASE}/search", json={"query": "test", "limit": 3}, headers=headers())
        check("POST /search 200 or 429", r.status_code in (200, 429), str(r.status_code))
        if r.status_code == 200:
            j = r.json()
            check("POST /search has results", "results" in j, "")
            # Second identical request: should hit cache (same response shape)
            r2 = client.post(f"{BASE}/search", json={"query": "test", "limit": 3}, headers=headers())
            check("POST /search repeat (cache) 200", r2.status_code == 200, str(r2.status_code))

        # Query: 200 or 429
        r = client.post(
            f"{BASE}/query",
            json={"query": "What books are available?", "skip_verification": True},
            headers=headers(),
        )
        check("POST /query 200 or 429", r.status_code in (200, 429), str(r.status_code))
        if r.status_code == 429:
            check("429 has Retry-After", "Retry-After" in r.headers, "")

        # skip_cache: both search and query accept skip_cache
        r = client.post(
            f"{BASE}/search",
            json={"query": "other", "limit": 2, "skip_cache": True},
            headers=headers(),
        )
        check("POST /search skip_cache=true 200 or 429", r.status_code in (200, 429), str(r.status_code))

    print()
    print(f"Result: {ok} passed, {fail} failed")
    sys.exit(0 if fail == 0 else 1)


if __name__ == "__main__":
    main()
