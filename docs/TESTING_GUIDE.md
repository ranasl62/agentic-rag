# Testing Guide

> How to test the **whole** Agentic RAG application: Phase 1–6 unit tests, live validation scripts, E2E flows, and manual checks.

**Quick links:** [Unit tests](#1-unit-tests-pytest) · [Live validation](#2-live-validation-phase-1–6) · [E2E flow](#3-end-to-end-flow) · [Quick reference](#4-quick-reference)

---

## Test status summary

| Phase | Unit tests | Live validation | Notes |
|-------|------------|-----------------|--------|
| **1** | Data model & tenant: ✅ pass. Endpoint tests need Postgres. | `validate_phase1_live` — auth, /books, /sections, /search, /compare, /summarize, /query | Without DB: 7 errors (app lifespan). With stack: all pass. |
| **2** | Cache keys, rate limit, 429 response: ✅ pass. | `validate_phase2_live` — search, query, cache, skip_cache | 5 checks. |
| **3** | Job status set/get: ✅ pass. Endpoint tests need app. | `validate_phase3_live` — 202 + job_id, GET /ingest/status | Celery optional (sync 200 otherwise). |
| **4** | — | `validate_phase4_live` — health via Nginx, LB | API at **http://localhost:8080**. |
| **5** | PgBouncer URL config: ✅ pass. | `validate_phase5_live` — health, books, search, ingest status | Full stack. |
| **6** | Metrics helpers & endpoint, logging: ✅ pass. | `validate_phase6_live` — GET /metrics, request logging | METRICS_ENABLED=true. |

**Typical unit run (no Postgres):** `23 passed, 7 skipped, 7 errors` — errors from Phase 1 app startup (DB connect).  
**With Postgres + Redis:** More tests run; endpoint tests may still skip if env differs.

---

## 1. Unit tests (pytest)

Run all Phase 1–6 unit tests:

```bash
uv run pytest tests/test_phase1_validation.py tests/test_phase2_rate_limit_cache.py \
  tests/test_phase3_async_ingest.py tests/test_phase5_pgbouncer.py \
  tests/test_phase6_metrics.py tests/test_phase6_logging.py -v --tb=short
```

### What each file covers

| Test file | Covers |
|-----------|--------|
| `test_phase1_validation.py` | Tenant model, API key resolution; app startup + endpoints (need Postgres). |
| `test_phase2_rate_limit_cache.py` | Cache key generation, rate limit disabled/429; search/query with cache (need app + Redis). |
| `test_phase3_async_ingest.py` | Job status storage; GET /ingest/status and 202 upload (need app + Redis). |
| `test_phase5_pgbouncer.py` | Postgres/PgBouncer URL from env (no DB). |
| `test_phase6_metrics.py` | Status class, path normalization, /metrics content type and body. |
| `test_phase6_logging.py` | Request ID format, middleware callable and request_id on state. |

---

## 2. Live validation (Phase 1–6)

Scripts hit a **running** API (Postgres, Redis, Qdrant; optional Nginx, Celery, PgBouncer).  
**Base URL:** `http://localhost:8080` (Docker + Nginx) or `http://localhost:8000` (API only).

### Prerequisites

- `docker compose up -d` (or API + dependencies running).
- If `REQUIRE_AUTH=true`: create tenant and set `AGENT_API_KEY` ([below](#creating-an-api-key)).

### Run all phase validations

```bash
export API_BASE_URL=http://localhost:8080
# If auth enabled:
export AGENT_API_KEY=your-api-key

uv run python -m scripts.validate_phase1_live
uv run python -m scripts.validate_phase2_live
uv run python -m scripts.validate_phase3_live
uv run python -m scripts.validate_phase4_live
uv run python -m scripts.validate_phase5_live
uv run python -m scripts.validate_phase6_live
```

### What each script checks

| Script | Checks |
|--------|--------|
| **Phase 1** | /health, /books, /books/sections, /search, /compare, /summarize, /query; auth (401 without key when required). |
| **Phase 2** | Search & query 200; cache hit on repeat; skip_cache bypass; 429 when rate limited. |
| **Phase 3** | Upload async_mode=1 → 202 + job_id; GET /ingest/status/{job_id} → pending/completed/failed. |
| **Phase 4** | /health via Nginx; load balancing across replicas. |
| **Phase 5** | Health, /books, /search, /ingest/status through full stack (PgBouncer). |
| **Phase 6** | GET /metrics (Prometheus); structured request logging. |

### Creating an API key

```bash
POSTGRES_HOST=localhost POSTGRES_PORT=5433 uv run python -m scripts.create_tenant "Test Tenant" test-tenant
```

Use the printed key as `AGENT_API_KEY` for live scripts.

---

## 3. End-to-end flow

Full RAG path: **upload → list books → search → compare → query**.

1. **Start stack & tenant**  
   `docker compose up -d` → create tenant → set `API_BASE_URL` and `AGENT_API_KEY`.

2. **Upload two editions**  
   `POST /upload/document` (file, title, author, edition_name) for each file.

3. **List books**  
   `GET /books` → note `book_id` and `edition_id`s.

4. **Search**  
   `POST /search` with `{"query": "...", "limit": 5}`.

5. **Compare**  
   `POST /compare` with `book_id`, `chapter_number`, `section_number`, `edition_ids`.

6. **Full pipeline**  
   `POST /query` with natural-language question.

Detailed curl examples: [VALIDATION_PHASE1_PHASE2_PHASE3.md](VALIDATION_PHASE1_PHASE2_PHASE3.md) and [USER_GUIDE.md](USER_GUIDE.md).

---

## 4. Quick reference

| Goal | Command |
|------|---------|
| **All unit tests** | `uv run pytest tests/test_phase1_validation.py tests/test_phase2_rate_limit_cache.py tests/test_phase3_async_ingest.py tests/test_phase5_pgbouncer.py tests/test_phase6_metrics.py tests/test_phase6_logging.py -v` |
| **All live** | `export API_BASE_URL=http://localhost:8080` then run `validate_phase1_live` … `validate_phase6_live` |
| **Create API key** | `POSTGRES_HOST=localhost POSTGRES_PORT=5433 uv run python -m scripts.create_tenant "Name" slug` |
| **Swagger** | http://localhost:8080/docs (or 8000) |
| **Chat** | `API_BASE_URL=http://localhost:8080 AGENT_API_KEY=key uv run python -m scripts.chat` |

---

## 5. Manual testing

- **Swagger UI:** http://localhost:8080/docs — try /health, /books, /search, /upload/document, /query.
- **Web UI:** http://localhost:3001 (if Next.js running).
- **Chat:** `uv run python -m scripts.chat` with `API_BASE_URL` and `AGENT_API_KEY` set.

For phase-by-phase expectations and troubleshooting, see [VALIDATION_PHASE1_PHASE2_PHASE3.md](VALIDATION_PHASE1_PHASE2_PHASE3.md) and [PHASE1_PHASE6_ALIGNMENT.md](PHASE1_PHASE6_ALIGNMENT.md).
