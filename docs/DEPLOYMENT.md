# Production Deployment

How to run Agentic RAG at scale: multi-tenant auth, rate limiting, caching, async ingestion, horizontal scaling, and monitoring. Each layer can be adopted incrementally.

---

## Overview

| Layer | Purpose |
|-------|--------|
| **1. Auth + tenants** | API key per tenant; data and search scoped by tenant. |
| **2. Rate limit + cache** | Redis: per-tenant rate limits; cache for search/query to protect and speed up the API. |
| **3. Async ingestion** | Celery + Redis: upload returns 202 + job_id; workers run the pipeline; poll `GET /ingest/status/{job_id}`. |
| **4. API scaling** | Nginx (or other LB) in front; run multiple API replicas (`--scale api-service=N`). |
| **5. Data layer** | PgBouncer for Postgres connection pooling; size Qdrant/Postgres and document backup/restore. |
| **6. Monitoring** | Prometheus `GET /metrics`, structured logging (request_id, tenant_id), alerts and dashboards. |

**Runbooks:** See [Operations](OPERATIONS.md) for scaling, backup/restore, failover, and monitoring details.

---

## Quick reference

- **Env:** `.env` from `.env.example`; set `POSTGRES_PASSWORD`, and optionally `REQUIRE_AUTH`, rate limits, cache TTLs, `METRICS_ENABLED`, `API_PORT=8080` when behind Nginx.
- **Tenants:** `scripts/create_tenant.py` to create a tenant and get an API key; use `X-API-Key` on requests.
- **Scale API:** `docker compose up -d --scale api-service=2`
- **Scale workers:** `docker compose up -d --scale celery-worker=2`
- **Metrics:** `GET /metrics` (Prometheus); enable with `METRICS_ENABLED=true`

Validation scripts (run against a live API at `http://localhost:8080`):

```bash
uv run python -m scripts.validate_phase1_live
uv run python -m scripts.validate_phase2_live
# ... through validate_phase6_live
```

See [Testing guide](TESTING_GUIDE.md) for full test and validation instructions.
