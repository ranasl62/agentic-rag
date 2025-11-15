# Phase 1–6 Alignment and Sync

Single reference for how all six phases align with the roadmap, docs, scripts, and tests.

---

## Overview

| Phase | Focus | Roadmap status | Key docs | Scripts / tests |
|-------|--------|----------------|----------|------------------|
| **1** | Auth + tenant isolation | Done | PHASE1_AUTH_TENANTS.md | create_tenant.py, backfill_tenant.py, validate_phase1_live.py, test_phase1_validation.py |
| **2** | Rate limiting + Redis cache | Done | PHASE2_RATE_LIMIT_CACHE.md | validate_phase2_live.py, test_phase2_rate_limit_cache.py |
| **3** | Async ingestion (Celery) | Done | PHASE3_ASYNC_INGESTION.md | validate_phase3_live.py, test_phase3_async_ingest.py |
| **4** | API scaling (Nginx + replicas) | Done | PHASE4_API_SCALING.md | validate_phase4_live.py |
| **5** | Qdrant + Postgres (PgBouncer, backup) | Done | PHASE5_QDRANT_POSTGRES_SCALING.md, runbooks/ | validate_phase5_live.py, test_phase5_pgbouncer.py |
| **6** | Monitoring, alerts, runbooks | Done | PHASE6_MONITORING_ALERTS.md, runbooks/monitoring.md | validate_phase6_live, test_phase6_metrics.py, test_phase6_logging.py |

---

## Phase 1: Auth + Tenant Isolation

- **Deliverables (all [x]):** tenants table, tenant_id on books + Qdrant, auth (API key), get_current_tenant, all paths scoped, create_tenant + backfill, PHASE1 doc.
- **Code:** `src/api/auth.py`, `src/storage/models.py`, tenant_id in routes and tools, Qdrant filters.
- **Validation:** `scripts/validate_phase1_live.py`; `pytest tests/test_phase1_validation.py`.

---

## Phase 2: Rate Limiting + Redis Caching

- **Deliverables (all [x]):** Rate limit dependency (Redis), per-tenant + optional per-IP; search + query cache; skip_cache; env config; PHASE2 doc.
- **Code:** `src/api/rate_limit.py`, `src/api/cache.py`, applied to search, query, upload, compare, summarize, list.
- **Validation:** `scripts/validate_phase2_live.py`; `pytest tests/test_phase2_rate_limit_cache.py`.

---

## Phase 3: Async Ingestion

- **Deliverables (all [x]):** Celery app + Redis broker, ingest_document_task; upload async_mode=1 → 202 + job_id; job status in Redis + GET /ingest/status/{job_id}; Docker celery-worker; PHASE3 doc.
- **Code:** `src/worker/celery_app.py`, `src/worker/ingest_runner.py`, upload route, ingest router.
- **Validation:** `scripts/validate_phase3_live.py`; `pytest tests/test_phase3_async_ingest.py`.

---

## Phase 4: API Scaling

- **Deliverables (all [x]):** Stateless API (audit); Nginx LB with health and proxy_next_upstream; api-service behind Nginx, scale with --scale api-service=N; PHASE4 doc.
- **Code:** `docker/nginx.conf`, docker-compose nginx + api-service expose only.
- **Validation:** `scripts/validate_phase4_live.py`. Use `API_BASE_URL=http://localhost:8080` (Nginx).

---

## Phase 5: Qdrant + Postgres Scaling

- **Deliverables (all [x]):** PgBouncer in Docker; API and Celery connect via PgBouncer; Qdrant/Postgres sizing and backup/restore documented; runbooks (add-capacity, backup-restore, failover).
- **Code:** docker-compose pgbouncer service; API/Celery POSTGRES_HOST=pgbouncer, POSTGRES_PORT=6432.
- **Docs:** PHASE5_QDRANT_POSTGRES_SCALING.md; docs/runbooks/add-capacity.md, backup-restore.md, failover.md.
- **Validation:** `scripts/validate_phase5_live.py`; `pytest tests/test_phase5_pgbouncer.py`. Use `API_BASE_URL=http://localhost:8080`.

---

## Phase 6: Monitoring, Alerts, Runbooks

- **Deliverables:**
  - [x] **Runbooks:** add-capacity, backup-restore, failover, monitoring (docs/runbooks/).
  - [x] **Prometheus metrics:** GET /metrics (http_requests_total, http_request_duration_seconds); docs/runbooks/monitoring.md.
  - [x] **Structured logging:** request_id, tenant_id, endpoint, status_code, duration_ms (structlog JSON); LOG_LEVEL config.
  - [x] **Alerts and dashboards:** documented in docs/runbooks/monitoring.md (alert rules, Grafana panels, channels).

---

## Validation and Test Commands (unified)

With **Docker stack** (Nginx on 8080), use `API_BASE_URL=http://localhost:8080` for all live scripts:

| Phase | Unit tests | Live validation |
|-------|------------|------------------|
| 1 | `pytest tests/test_phase1_validation.py -v` | `API_BASE_URL=http://localhost:8080 uv run python -m scripts.validate_phase1_live` |
| 2 | `pytest tests/test_phase2_rate_limit_cache.py -v` | `API_BASE_URL=http://localhost:8080 uv run python -m scripts.validate_phase2_live` |
| 3 | `pytest tests/test_phase3_async_ingest.py -v` | `API_BASE_URL=http://localhost:8080 uv run python -m scripts.validate_phase3_live` |
| 4 | — | `API_BASE_URL=http://localhost:8080 uv run python -m scripts.validate_phase4_live` |
| 5 | `pytest tests/test_phase5_pgbouncer.py -v` | `API_BASE_URL=http://localhost:8080 uv run python -m scripts.validate_phase5_live` |
| 6 | `pytest tests/test_phase6_metrics.py tests/test_phase6_logging.py -v` | `API_BASE_URL=http://localhost:8080 uv run python -m scripts.validate_phase6_live` |

---

## Doc and Script Index

| Asset | Purpose |
|-------|---------|
| PRODUCTION_ROADMAP_60K.md | Master plan Phases 1–6 |
| PHASE1_AUTH_TENANTS.md | Phase 1 spec and tasks |
| PHASE2_RATE_LIMIT_CACHE.md | Phase 2 spec and config |
| PHASE3_ASYNC_INGESTION.md | Phase 3 spec and API |
| PHASE4_API_SCALING.md | Phase 4 stateless + Nginx |
| PHASE5_QDRANT_POSTGRES_SCALING.md | Phase 5 PgBouncer + backup |
| runbooks/add-capacity.md | Scale replicas, workers, resources |
| runbooks/backup-restore.md | Postgres and Qdrant backup/restore |
| runbooks/failover.md | Recovery when components are down |
| VALIDATION_PHASE1_PHASE2_PHASE3.md | How to run Phase 1–6 checks and tests |
| PHASE1_PHASE4_COMPLETENESS.md | Detailed audit Phase 1–4 (optional improvements) |
| PHASE6_MONITORING_ALERTS.md | Phase 6 plan, test cases, implementation summary |
| runbooks/monitoring.md | Metrics scrape, alert rules, dashboards, logging |
| PHASE1_PHASE6_ALIGNMENT.md | This file: alignment of all phases |
