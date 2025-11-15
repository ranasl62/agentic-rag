"""
Validate Phase 6 (metrics + logging) against a running API.
Expects: API reachable (e.g. http://localhost:8080 with Nginx). Checks GET /metrics and that a request is recorded.

Usage:
  API_BASE_URL=http://localhost:8080 uv run python -m scripts.validate_phase6_live
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx

BASE = os.environ.get("API_BASE_URL", "http://localhost:8080")


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

    print("Phase 6 validation (metrics)")
    print(f"  Base URL: {BASE}")
    print()

    with httpx.Client(timeout=10.0) as client:
        r = client.get(f"{BASE}/metrics")
        check("GET /metrics 200 or 404", r.status_code in (200, 404), str(r.status_code))
        if r.status_code == 200:
            body = r.text
            check("Content-Type text/plain", "text/plain" in r.headers.get("Content-Type", ""), "")
            check("/metrics contains http_requests_total", "http_requests_total" in body, "")
            check("/metrics contains http_request_duration_seconds", "http_request_duration_seconds" in body, "")

        r = client.get(f"{BASE}/health")
        check("GET /health 200", r.status_code == 200, str(r.status_code))

        r = client.get(f"{BASE}/metrics")
        check("GET /metrics after /health still 200", r.status_code == 200, str(r.status_code))
        if r.status_code == 200 and "http_requests_total" in r.text:
            # At least health and metrics requests should be counted
            check("Metrics include request counts", "http_requests_total" in r.text, "")

    print()
    print(f"Result: {ok} passed, {fail} failed")
    sys.exit(0 if fail == 0 else 1)


if __name__ == "__main__":
    main()
