# Production Roadmap: 60k Dealers + Lots of Manuals

This document is a phased plan to take the Agentic RAG system to production scale: **60k dealer users**, **many repair manuals**, with auth, tenant isolation, rate limiting, caching, async ingestion, horizontal scaling, and observability.

---

## Overview

| Phase | Focus | Outcome |
|-------|--------|---------|
| **1** | Auth + tenant isolation | Dealers only see their brand/manuals; secure API |
| **2** | Rate limiting + Redis caching | Protect APIs; reduce repeat load |
| **3** | Async ingestion (Celery + Redis) | Upload/embed without blocking; scale ingest |
| **4** | API scaling (replicas + LB) | Handle concurrent dealer traffic |
| **5** | Qdrant + Postgres scaling | Data and query capacity |
| **6** | Monitoring, alerts, runbooks | Operate and debug in prod |

Each phase can be done incrementally; later phases build on earlier ones.

**Alignment:** [docs/PHASE1_PHASE6_ALIGNMENT.md](docs/PHASE1_PHASE6_ALIGNMENT.md). **Completion/sync checklist:** [docs/PHASES_1_6_SYNC_CHECKLIST.md](docs/PHASES_1_6_SYNC_CHECKLIST.md).

---

## Phase 1: Auth + Tenant Isolation (Dealer/Brand)

**Goal:** Every request is tied to a **tenant** (dealer or brand). Data and search are scoped so dealers only access their manuals.

### 1.1 Data model changes

- **Tenant identity**
  - Add `tenant_id` (e.g. UUID or slug) to represent a dealer or brand.
  - Store in `Book` and/or `Edition` (or a new `Dealer` / `Brand` table linked to books).
- **Schema**
  - `tenants` table: `tenant_id`, `name`, `slug`, `brand_ids` (optional), `created_at`, `metadata` (JSON).
  - `books`: add `tenant_id` (FK to tenants); all existing books get a default “global” tenant if you need backward compatibility.
  - **Qdrant payloads:** add `tenant_id` to every section/chunk payload so search can filter by tenant.

### 1.2 Auth mechanism

- **Choose one (or combine):**
  - **API keys:** per-tenant API key; API validates key and resolves `tenant_id`. Simple for server-to-server (e.g. dealer portal backend calling your API).
  - **JWT:** dealer logs in; your auth service issues a JWT with `tenant_id` (and optionally `dealer_id`, `roles`). API validates JWT and extracts `tenant_id`.
  - **OAuth2 / OIDC:** if dealers already have an identity provider, integrate it and map identity → `tenant_id`.
- **Implementation**
  - Middleware or dependency that: validates API key or JWT, resolves `tenant_id`, attaches it to request state (e.g. `request.state.tenant_id`).
  - All routes that touch books/sections/search **must** use this `tenant_id` (filter DB and Qdrant).

### 1.3 Tenant isolation in code

- **Upload:** accept `tenant_id` from auth (or from validated claim); set `tenant_id` on created `Book`/`Edition` and in Qdrant payloads.
- **Search / query / compare / summarize:**
  - Postgres: `WHERE tenant_id = :tenant_id` on books/editions/sections.
  - Qdrant: add `tenant_id` to `filter_conditions` in every search so vectors are tenant-scoped.
- **List books/editions:** only return books for `request.state.tenant_id`.

### 1.4 Deliverables

- [x] `tenants` table + migration (init_db + scripts/backfill_tenant.py for existing DBs).
- [x] `tenant_id` on books and in Qdrant payloads; backfill script for existing DBs.
- [x] Auth (API key) and `get_current_tenant()` dependency (src/api/auth.py).
- [x] All read/write paths accept and enforce `tenant_id` (upload, books, sections, search, compare, summarize, query + tools).
- [x] Docs and script: docs/PHASE1_AUTH_TENANTS.md; scripts/create_tenant.py to create tenants and issue API keys.

**Document scope (country, brand, language, vehicle metadata with wildcards):** See [docs/DOCUMENT_SCOPE_AND_VEHICLE_METADATA.md](docs/DOCUMENT_SCOPE_AND_VEHICLE_METADATA.md) for design. Documents can be scoped by country, brand, language, and vehicle metadata (model year range, model code pattern like `C**`, engine, transmission with `*` = any). Implementation is a follow-on to Phase 1.

---

## Phase 2: Rate Limiting + Redis Caching

**Goal:** Protect the API from abuse and reduce load by caching repeated queries.

### 2.1 Rate limiting

- **Tool:** use Redis (you already have it) and a library such as `slowapi` or a custom middleware with `redis.incr` + TTL.
- **Policies (examples):**
  - Per tenant: e.g. 100 req/min for search, 20/min for query, 5/min for upload.
  - Per IP (optional): e.g. 200 req/min as a safety net.
- **Implementation**
  - Middleware or dependency that checks limits **after** auth (so limits are per tenant).
  - On exceed: return `429 Too Many Requests` with `Retry-After`.
- **Config:** make limits configurable via env (e.g. `RATE_LIMIT_SEARCH_PER_MIN=100`).

### 2.2 Caching (Redis)

- **What to cache**
  - **Search results:** key = `tenant_id + hash(query + filters + limit)`; TTL e.g. 5–15 minutes.
  - **Query (orchestrator) results:** key = `tenant_id + hash(query)`; TTL e.g. 2–5 minutes (optional, since answers can be long).
- **Implementation**
  - Before running search (or full query): check Redis for a cached result; if hit, return it.
  - After computing result: store in Redis with TTL.
  - Invalidate or use short TTL so manual updates (re-ingestion) don’t serve stale data too long.
- **Optional:** cache embedding for the query text (to avoid re-calling embed API for identical query); then only vector search is done per request (still tenant-scoped).

### 2.3 Deliverables

- [x] Rate limit middleware/dependency with Redis backend; per-tenant (and optional per-IP) limits.
- [x] Cache layer for search (and optionally query) with tenant-scoped keys and TTL.
- [x] Env-driven config for limits and TTLs.
- [x] Docs: limits per endpoint, cache TTL, invalidation strategy (see docs/PHASE2_RATE_LIMIT_CACHE.md).

---

## Phase 3: Async Ingestion (Celery + Redis)

**Goal:** Upload and ingestion (parse → chunk → embed → store) run in background so the API stays responsive and can scale ingest independently.

### 3.1 Queue and workers

- **Broker:** Redis (already in stack) as Celery broker; no need for RabbitMQ unless you prefer it.
- **Celery**
  - One (or more) Celery app(s) in the repo; same codebase as API, different process.
  - Tasks: e.g. `ingest_document_task(tenant_id, file_content_or_path, title, author, edition_name, ...)` that calls existing `IngestionPipeline` (sync) or an async-friendly variant.
- **Flow**
  1. **Upload API:** validate file + auth, store file temporarily (e.g. S3 or local volume) or pass content to task; enqueue `ingest_document_task` with `tenant_id` and metadata; return `202 Accepted` with a `job_id`.
  2. **Worker:** picks up task, runs parsing → chunking → embedding → Postgres + Qdrant; on success/failure updates job status (e.g. in Redis or a small `ingest_jobs` table).
  3. **Status API (optional):** `GET /ingest/status/{job_id}` for clients to poll until done.

### 3.2 Embedding in workers

- Workers run the same embedding code (Ollama or OpenAI) as today; ensure env (e.g. `OPENAI_API_KEY`, `EMBED_PROVIDER`) is available in the worker environment.
- For very large manuals, consider batching embed calls (e.g. by chunk batch) to avoid timeouts; existing `embed_batch` can be used or extended.

### 3.3 Tenant and vector store

- Pass `tenant_id` into the ingestion pipeline and set it on all created books/editions/sections and in Qdrant payloads (same as Phase 1).
- Ensure workers use the same Qdrant and Postgres as the API (same config/env).

### 3.4 Deliverables

- [x] Celery app + Redis broker; `ingest_document_task` (src/worker/celery_app.py).
- [x] Upload API: enqueue task when async_mode=1, return 202 + job_id.
- [x] Ingest job status in Redis + GET /ingest/status/{job_id}.
- [x] Docker: celery-worker service (same image as API).
- [x] Docs: docs/PHASE3_ASYNC_INGESTION.md; run worker: celery -A src.worker.celery_app worker -l info.

---

## Phase 4: API Scaling (Replicas + Load Balancer)

**Goal:** Run multiple API instances behind a load balancer so you can handle 60k dealers (and their concurrent requests).

### 4.1 Stateless API

- Ensure the API is **stateless:** no in-memory session or per-process state that must be shared. Auth is per-request (JWT or API key); tenant from token.
- Redis and DB are shared; any replica can serve any request.

### 4.2 Load balancer

- Put a **reverse proxy / load balancer** in front of the API (e.g. Nginx, Traefik, or cloud LB).
- Health check: existing `GET /health`; LB only sends traffic to healthy instances.
- TLS: terminate at LB or at API; recommend at LB.

### 4.3 Run multiple API replicas

- **Docker Compose:** e.g. `docker compose up -d --scale api-service=3`.
- **Kubernetes:** Deployment with `replicas: 5` (tune from load tests); Service in front.
- **Cloud:** ECS, EKS, or similar with auto-scaling based on CPU or request count.

### 4.4 Session affinity (optional)

- Usually **not** required for RAG (stateless). If you add sticky sessions later for other reasons, configure at LB.

### 4.5 Deliverables

- [x] Confirm API is stateless (no local-only state). See docs/PHASE4_API_SCALING.md.
- [x] Add/configure LB (Nginx) with health check and proxy_next_upstream; TLS optional (doc in PHASE4).
- [x] Run 2+ API replicas via `docker compose up -d --scale api-service=2`; traffic through Nginx on API_PORT (default 8080).
- [x] Docs: docs/PHASE4_API_SCALING.md; scripts/validate_phase4_live.py.

---

## Phase 5: Qdrant + Postgres Scaling

**Goal:** Support “lots of manuals” and higher QPS without becoming the bottleneck.

### 5.1 Qdrant

- **Single node (today):** fine for pilot; for production with millions of vectors:
  - **Option A:** Single node with enough RAM/disk; tune `indexing_threshold` and HNSW params if needed.
  - **Option B:** Qdrant cluster (replication + sharding) for high availability and larger data.
- **Collections:** you already have section + chunk collections. With tenants, **filter every search by `tenant_id`**; no need for a separate collection per tenant unless you want to isolate by collection (e.g. one collection per brand).
- **Backup:** schedule snapshots/backups of Qdrant data; document restore procedure.

### 5.2 Postgres

- **Connection pooling:** use PgBouncer (or equivalent) so many API replicas don’t exhaust DB connections.
- **Tuning:** `shared_buffers`, `work_mem`, etc. based on host RAM and workload.
- **Read scaling (optional):** add read replicas; route read-only queries (list books, get section) to replicas; writes (upload metadata, ingest) to primary.
- **Backup:** automated backups and point-in-time recovery; document restore and failover.

### 5.3 Deliverables

- [x] Qdrant: size and tune for expected vector count; document backup/restore (docs/PHASE5_QDRANT_POSTGRES_SCALING.md, docs/runbooks/backup-restore.md).
- [x] Postgres: PgBouncer in front in Docker; API and Celery connect via PgBouncer; tune/backup documented; optional read replicas (doc only).
- [x] Runbooks: add capacity, backup-restore, failover (docs/runbooks/add-capacity.md, backup-restore.md, failover.md).

---

## Phase 6: Monitoring, Alerts, Runbooks

**Goal:** Know when things break, why, and what to do.

### 6.1 Metrics

- **API:** request count, latency (p50/p95/p99), error rate by endpoint and status (e.g. 5xx).
- **Queue:** Celery queue length, task success/failure rate, task duration.
- **Infra:** CPU, memory, disk for API, workers, Qdrant, Postgres, Redis.
- **Tool:** Prometheus + Grafana, or cloud metrics (CloudWatch, etc.). Instrument the API (e.g. `prometheus_client`) and export `/metrics`; scrape from Prometheus or cloud agent.

### 6.2 Logging

- **Structured logs:** JSON logs with `tenant_id`, `request_id`, `endpoint`, `duration`, `error`. Use your existing `structlog` or similar; ensure level is configurable (e.g. INFO in prod, DEBUG in staging).
- **Central log store:** ship logs to a central store (e.g. Loki, Elasticsearch, or cloud logging) so you can search by tenant, request_id, or error.

### 6.3 Alerts

- **Examples:** API error rate > 5%; p95 latency > 10s; Celery queue length > 1000; Qdrant/Postgres/Redis down; disk > 85%.
- **Channel:** PagerDuty, Slack, or email; document who is on-call and escalation.

### 6.4 Runbooks

- **Document:** how to restart services, scale replicas, clear cache, drain queue, restore DB/Qdrant from backup, roll back a deploy, debug “no results” (check tenant_id, embedding model, Qdrant filter).
- **Location:** wiki or `docs/runbooks/` in the repo. Implemented: docs/runbooks/add-capacity.md, backup-restore.md, failover.md, monitoring.md.

### 6.5 Deliverables

- [x] Prometheus metrics for API (GET /metrics: http_requests_total, http_request_duration_seconds); doc and dashboards (docs/runbooks/monitoring.md).
- [x] Structured logging with request_id, tenant_id, endpoint, status_code, duration_ms (structlog JSON; docs/PHASE6_MONITORING_ALERTS.md).
- [x] Alerts and dashboards documented (docs/runbooks/monitoring.md: alert rules, Grafana panels, channels).
- [x] Runbooks for common operations and incidents (docs/runbooks/: add-capacity, backup-restore, failover, monitoring).

---

## Implementation Order and Dependencies

```
Phase 1 (Auth + Tenant)  ──►  Phase 2 (Rate limit + Cache)
        │                              │
        └──────────────┬───────────────┘
                       ▼
              Phase 3 (Async ingest)
                       │
                       ▼
              Phase 4 (API scaling)
                       │
                       ▼
              Phase 5 (Qdrant + Postgres)
                       │
                       ▼
              Phase 6 (Monitoring + Runbooks)
```

- **Phase 1** is the foundation: without tenant isolation, caching and scaling are harder to reason about.
- **Phase 2** can start once you have at least a placeholder tenant (e.g. single tenant) so cache keys and rate limits can be tenant-scoped.
- **Phase 3** depends on Phase 1 so tasks run with correct `tenant_id`.
- **Phases 4–6** can overlap; e.g. add basic monitoring early, then add scaling and more alerts.

---

## Suggested Timeline (High Level)

| Phase | Suggested duration (order-of-magnitude) |
|-------|----------------------------------------|
| 1. Auth + tenant | 2–4 weeks |
| 2. Rate limit + cache | 1–2 weeks |
| 3. Async ingest | 2–3 weeks |
| 4. API scaling | ~1 week |
| 5. Qdrant + Postgres | 1–2 weeks |
| 6. Monitoring + runbooks | Ongoing; initial 1–2 weeks |

Total to “production-ready” for 60k + lots of manuals: on the order of **2–3 months** with one focused engineer, or shorter with a small team.

---

## Checklist Summary

- [x] **Phase 1:** Tenants, `tenant_id` in data and Qdrant; auth (API key); all paths tenant-scoped (see docs/PHASE1_AUTH_TENANTS.md).
- [x] **Phase 2:** Redis rate limiting per tenant (and optional per-IP); Redis cache for search and query (docs/PHASE2_RATE_LIMIT_CACHE.md).
- [x] **Phase 3:** Celery + Redis; upload enqueues ingest task; workers run pipeline; GET /ingest/status (docs/PHASE3_ASYNC_INGESTION.md).
- [x] **Phase 4:** Stateless API; Nginx LB; 2+ replicas via --scale api-service=N; health checks (docs/PHASE4_API_SCALING.md).
- [x] **Phase 5:** Qdrant sizing/backup doc; PgBouncer in Docker; Postgres backup/restore; runbooks (docs/PHASE5_QDRANT_POSTGRES_SCALING.md, docs/runbooks/).
- [x] **Phase 6:** Prometheus /metrics; structured logging (request_id, tenant_id); alerts/dashboards doc (docs/PHASE6_MONITORING_ALERTS.md, docs/runbooks/monitoring.md).

**Phase 1–6 alignment:** See [docs/PHASE1_PHASE6_ALIGNMENT.md](docs/PHASE1_PHASE6_ALIGNMENT.md) for how all phases align with docs, scripts, and tests. Phase 1–4 detail: [docs/PHASE1_PHASE4_COMPLETENESS.md](docs/PHASE1_PHASE4_COMPLETENESS.md).

**Status:** All six phases are complete. Validation: run unit tests per phase (see alignment doc) and live scripts with `API_BASE_URL=http://localhost:8080` when the Docker stack is up.
