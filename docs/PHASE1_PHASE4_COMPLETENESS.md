# Phase 1–4 Completeness Checklist

Audit of what is done and what (if anything) remains or is optional. For Phase 1–6 alignment (docs, scripts, tests), see [PHASE1_PHASE6_ALIGNMENT.md](PHASE1_PHASE6_ALIGNMENT.md).

---

## Phase 1: Auth + Tenant Isolation

| Deliverable | Status | Notes |
|-------------|--------|--------|
| `tenants` table + init_db + backfill_tenant.py | Done | `src/storage/models.py`, `postgres_client.py`, `scripts/backfill_tenant.py` |
| `tenant_id` on books, Qdrant payloads and filters | Done | Books, ingestion, qdrant_client |
| Auth (API key) + `get_current_tenant()` | Done | `src/api/auth.py` |
| Upload, books, sections, search, compare, summarize, query + tools scoped by tenant | Done | All routes and tools use tenant_id |
| create_tenant.py, PHASE1_AUTH_TENANTS.md | Done | Script and doc present |

**Optional / minor:**

- **GET /ingest/status/{job_id}** (Phase 3) has no auth. Job IDs are UUIDs (hard to guess). For strict tenant isolation you could store `tenant_id` in the job payload and require auth + tenant match. Not required by roadmap.
- **GET /debug/vector-status** requires auth (`get_current_tenant`) so it is consistent with Phase 1.

---

## Phase 2: Rate Limiting + Redis Caching

| Deliverable | Status | Notes |
|-------------|--------|--------|
| Rate limit dependency + Redis, per-tenant | Done | `src/api/rate_limit.py` |
| Per-IP limit (optional) | Done | `RATE_LIMIT_IP_PER_MIN`, checked in rate_limit.py |
| Cache for search and query, tenant-scoped, TTL | Done | `src/api/cache.py`, search.py, main.py |
| skip_cache on search and query | Done | Request body fields |
| Config (env) for limits and TTLs | Done | `config/settings.py`, `.env.example` |
| PHASE2_RATE_LIMIT_CACHE.md, validate_phase2_live.py | Done | Doc and script |

**Nothing left.**

---

## Phase 3: Async Ingestion

| Deliverable | Status | Notes |
|-------------|--------|--------|
| Celery app + Redis broker, ingest_document_task | Done | `src/worker/celery_app.py` |
| Upload async_mode=1 → 202 + job_id | Done | `src/api/routes/upload.py` |
| Job status in Redis, GET /ingest/status/{job_id} | Done | celery_app set/get_job_status, ingest router |
| Docker celery-worker service | Done | docker-compose.yml |
| PHASE3_ASYNC_INGESTION.md, validate_phase3_live.py | Done | Doc and script |

**Nothing left.** (Optional: auth for status endpoint — see Phase 1.)

---

## Phase 4: API Scaling

| Deliverable | Status | Notes |
|-------------|--------|--------|
| API stateless (audit) | Done | docs/PHASE4_API_SCALING.md |
| Nginx LB, health, proxy_next_upstream | Done | docker/nginx.conf, nginx service |
| api-service behind Nginx, no published port, scale with --scale | Done | docker-compose.yml |
| PHASE4_API_SCALING.md, validate_phase4_live.py | Done | Doc and script |

**Nothing left.**

---

## Summary

- **Phase 1, 2, 3, 4:** All roadmap deliverables are implemented.
- **Phase 5, 6:** See [PHASE5_QDRANT_POSTGRES_SCALING.md](PHASE5_QDRANT_POSTGRES_SCALING.md) and [PHASE6_MONITORING_ALERTS.md](PHASE6_MONITORING_ALERTS.md); runbooks in docs/runbooks/; metrics and logging in Phase 6.
- **Optional improvement:** Require auth on GET /ingest/status and optionally restrict by tenant. GET /debug/vector-status is auth-protected.
