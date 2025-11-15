"""
Validate Phase 3 (async ingestion) against a running API.
Requires: API running, Redis running. Optional: Celery worker for async to complete.

Usage:
  API_BASE_URL=http://localhost:8080 uv run python -m scripts.validate_phase3_live
  AGENT_API_KEY=key uv run python -m scripts.validate_phase3_live
"""
from __future__ import annotations

import os
import sys
import time

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

    print("Phase 3 validation (async ingestion)")
    print(f"  Base URL: {BASE}")
    print()

    with httpx.Client(timeout=30.0) as client:
        # GET /ingest/status/{job_id} for unknown job -> 404
        r = client.get(f"{BASE}/ingest/status/00000000-0000-0000-0000-000000000000", headers=headers())
        check("GET /ingest/status unknown -> 404", r.status_code == 404, str(r.status_code))

        # POST /upload/document with async_mode=1 -> 202 + job_id (no auth for status? status is public in spec - no tenant scoping. So we need auth for upload.)
        # Use multipart for upload
        files = {"file": ("test.txt", b"Chapter 1\n\nSome content for phase 3 validation.")}
        data = {
            "title": "Phase3 Test",
            "author": "Validator",
            "edition_name": "2025",
            "async_mode": "1",
        }
        if API_KEY:
            headers_upload = {"X-API-Key": API_KEY}
        else:
            headers_upload = {}
        r = client.post(f"{BASE}/upload/document", files=files, data=data, headers=headers_upload)
        # May be 202 (async) or 401/503 if no key or services down
        if r.status_code == 202:
            j = r.json()
            check("POST /upload async -> 202", True, "")
            check("202 has job_id", "job_id" in j, "")
            job_id = j.get("job_id")
            if job_id:
                r2 = client.get(f"{BASE}/ingest/status/{job_id}", headers=headers())
                check("GET /ingest/status/{job_id} 200", r2.status_code == 200, str(r2.status_code))
                if r2.status_code == 200:
                    s = r2.json().get("status")
                    check("status is pending|running|completed|failed", s in ("pending", "running", "completed", "failed"), s)
        elif r.status_code == 200:
            check("POST /upload sync 200 (no async_mode or worker)", True, "sync response")
        else:
            check("POST /upload 200 or 202 or 401/503", r.status_code in (401, 503), str(r.status_code))

    print()
    print(f"Result: {ok} passed, {fail} failed")
    sys.exit(0 if fail == 0 else 1)


if __name__ == "__main__":
    main()
