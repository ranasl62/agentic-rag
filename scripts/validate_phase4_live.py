"""
Validate Phase 4 (API scaling: LB + replicas) against a running stack.
Expects: Nginx on API_BASE_URL (default http://localhost:8080); 1+ api-service replicas behind it.

Usage:
  API_BASE_URL=http://localhost:8080 uv run python -m scripts.validate_phase4_live
  AGENT_API_KEY=key uv run python -m scripts.validate_phase4_live
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

    print("Phase 4 validation (LB + API scaling)")
    print(f"  Base URL: {BASE} (expect Nginx LB)")
    print()

    with httpx.Client(timeout=15.0) as client:
        r = client.get(f"{BASE}/health")
        check("GET /health via LB returns 200", r.status_code == 200, str(r.status_code))
        if r.status_code == 200:
            check("Health body has status", isinstance(r.json(), dict) and "status" in r.json(), "")

        r = client.get(f"{BASE}/books", headers=headers())
        check("GET /books via LB: 200 or 401/503", r.status_code in (200, 401, 503), str(r.status_code))

        r = client.post(f"{BASE}/search", json={"query": "test", "limit": 2}, headers=headers())
        check("POST /search via LB: 200 or 401/503/429", r.status_code in (200, 401, 503, 429), str(r.status_code))

        # Multiple requests to confirm LB distributes (no assertion on which backend; just no errors)
        for i in range(3):
            r = client.get(f"{BASE}/health")
            check(f"GET /health repeat {i+1} 200", r.status_code == 200, str(r.status_code))

    print()
    print(f"Result: {ok} passed, {fail} failed")
    sys.exit(0 if fail == 0 else 1)


if __name__ == "__main__":
    main()
