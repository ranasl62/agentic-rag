# Phase 1–6: Feature Check and Test Guide

> How to run Phase 1–6 unit tests and live validation scripts. For a single testing hub, see [Testing guide](TESTING_GUIDE.md).

**Quick links:** [Prerequisites](#prerequisites) · [Unit tests](#1-unit-tests) · [Live validation](#2-live-validation) · [API key](#3-creating-an-api-key) · [Summary table](#4-quick-summary)

---

## Prerequisites

| Context | Requirement |
|---------|-------------|
| **Unit tests** | No services for cache/rate-limit/job-status/PgBouncer/metrics/logging tests. Phase 1 endpoint tests need **Postgres** (same credentials as API). |
| **Live validation** | **API running** (e.g. `docker compose up -d`). Base URL: **http://localhost:8080** (Nginx) or **http://localhost:8000** (API only). Optional: Celery for Phase 3 async; PgBouncer for Phase 5. |
| **Auth** | If `REQUIRE_AUTH=true`, set `AGENT_API_KEY` (create tenant [below](#3-creating-an-api-key)). |

---

## 1. Unit tests

```bash
uv run pytest tests/test_phase1_validation.py tests/test_phase2_rate_limit_cache.py \
  tests/test_phase3_async_ingest.py tests/test_phase5_pgbouncer.py \
  tests/test_phase6_metrics.py tests/test_phase6_logging.py -v --tb=short
```

### Expected results

| Environment | Phase 1 | Phase 2 | Phase 3 | Phase 5 | Phase 6 |
|-------------|---------|---------|---------|---------|---------|
| **No Postgres** | Data-model ✅; endpoint tests ERROR (lifespan/DB) | Cache/rate limit ✅; endpoint SKIP | Job status ✅; endpoint SKIP | ✅ | ✅ |
| **Postgres + Redis** | More tests run; may still skip if env differs | Same | Same | ✅ | ✅ |

**Typical run without Postgres:** `23 passed, 7 skipped, 7 errors` (errors from Phase 1 app startup).

---

## 2. Live validation

Point at your running API. Use `API_BASE_URL=http://localhost:8080` with Docker (Nginx); otherwise `http://localhost:8000`. With auth, set `AGENT_API_KEY`.

### Phase 1 (Auth + tenant isolation)

```bash
API_BASE_URL=http://localhost:8080 uv run python -m scripts.validate_phase1_live
# With API key:
AGENT_API_KEY=<your-key> API_BASE_URL=http://localhost:8080 uv run python -m scripts.validate_phase1_live
```

- **Without key:** Script accepts 200/401/503 for GET /books (depends on `REQUIRE_AUTH`).
- **With key:** All protected endpoints should return 200 when key is valid.
- **POST /summarize** may return 500 if LLM is unavailable → script reports failure.

### Phase 2 (Rate limit + cache)

```bash
API_BASE_URL=http://localhost:8080 uv run python -m scripts.validate_phase2_live
```

Expect: **5 passed, 0 failed** (search, query, cache, skip_cache).

### Phase 3 (Async ingestion)

```bash
API_BASE_URL=http://localhost:8080 uv run python -m scripts.validate_phase3_live
```

- **With Celery worker:** async_mode=1 → 202 + job_id; status pollable.
- **Without worker:** Sync 200; script still passes.

### Phase 4 (API scaling)

```bash
API_BASE_URL=http://localhost:8080 uv run python -m scripts.validate_phase4_live
```

Scale: `docker compose up -d --scale api-service=2`. See [Phase 4 API scaling](PHASE4_API_SCALING.md).

### Phase 5 (PgBouncer + stack)

```bash
API_BASE_URL=http://localhost:8080 uv run python -m scripts.validate_phase5_live
```

See [Phase 5 Qdrant/Postgres](PHASE5_QDRANT_POSTGRES_SCALING.md) and [runbooks](runbooks/).

### Phase 6 (Metrics)

```bash
API_BASE_URL=http://localhost:8080 uv run python -m scripts.validate_phase6_live
```

GET /metrics (Prometheus), request logging. See [Phase 6 monitoring](PHASE6_MONITORING_ALERTS.md) and [runbooks/monitoring](runbooks/monitoring.md).

---

## 3. Creating an API key

Tenants table must exist (API or backfill has run). From the host, same Postgres as API (e.g. port 5433):

```bash
POSTGRES_HOST=localhost POSTGRES_PORT=5433 uv run python -m scripts.create_tenant "Validation Tenant" validation
```

Use the printed key as `AGENT_API_KEY` for live scripts.

---

## 4. Quick summary

| Check | Command |
|-------|---------|
| Phase 1 unit | `uv run pytest tests/test_phase1_validation.py -v` |
| Phase 2 unit | `uv run pytest tests/test_phase2_rate_limit_cache.py -v` |
| Phase 3 unit | `uv run pytest tests/test_phase3_async_ingest.py -v` |
| Phase 5 unit | `uv run pytest tests/test_phase5_pgbouncer.py -v` |
| Phase 6 unit | `uv run pytest tests/test_phase6_metrics.py tests/test_phase6_logging.py -v` |
| Phase 1 live | `API_BASE_URL=http://localhost:8080 uv run python -m scripts.validate_phase1_live` |
| Phase 2 live | `API_BASE_URL=http://localhost:8080 uv run python -m scripts.validate_phase2_live` |
| Phase 3 live | `API_BASE_URL=http://localhost:8080 uv run python -m scripts.validate_phase3_live` |
| Phase 4 live | `API_BASE_URL=http://localhost:8080 uv run python -m scripts.validate_phase4_live` |
| Phase 5 live | `API_BASE_URL=http://localhost:8080 uv run python -m scripts.validate_phase5_live` |
| Phase 6 live | `API_BASE_URL=http://localhost:8080 uv run python -m scripts.validate_phase6_live` |

**With full stack up:** Phase 1 live 8–10 passed (summarize may 500 if LLM down); Phase 2 live 5 passed; Phase 3 live 2 passed; Phase 4–6 live as per scripts.
