# Phase 5: Qdrant + Postgres Scaling

**Goal:** Support “lots of manuals” and higher QPS: connection pooling for Postgres, Qdrant sizing/tuning, backup/restore, and runbooks.

---

## 5.1 Plan Overview

| Area | Scope | Deliverables |
|------|--------|---------------|
| **Postgres** | Connection pooling so many API replicas don’t exhaust DB connections | PgBouncer in front of Postgres; API and Celery connect via PgBouncer in Docker |
| **Postgres** | Tuning and backup | Document key params and backup/restore procedure |
| **Qdrant** | Sizing, tuning, backup | Document vector count sizing, HNSW/indexing, and snapshot/restore |
| **Runbooks** | Operations | Add capacity, restore from backup, failover |

---

## 5.2 Postgres: PgBouncer

### Why

- Multiple API replicas and Celery workers each hold Postgres connections. Without a pooler, high replica count can exhaust `max_connections`.
- PgBouncer holds a smaller pool to Postgres and multiplexes client connections (transaction pooling).

### Implementation

- **Docker:** Add `pgbouncer` service (Bitnami image). It connects to `postgres:5432` and listens on `6432`.
- **API and Celery:** In Docker Compose, set `POSTGRES_HOST=pgbouncer` and `POSTGRES_PORT=6432` so app and worker use the pooler.
- **Admin/scripts on host:** Keep using `POSTGRES_HOST=localhost` and `POSTGRES_PORT=5433` (published Postgres port) for migrations, backfill, create_tenant.

### Config

- **Pool mode:** `transaction` (works with asyncpg and Celery).
- **Auth:** Same user/password as Postgres; PgBouncer uses them to connect to the backend.

### Optional: bypass in dev

- To talk to Postgres directly from API (e.g. local dev without PgBouncer), set `POSTGRES_HOST=postgres` and `POSTGRES_PORT=5432` (or `localhost` and `5433` from host). Phase 5 Compose uses PgBouncer by default.

---

## 5.3 Postgres: Tuning and Backup

### Tuning (reference)

- **shared_buffers:** ~25% of RAM for dedicated DB host.
- **work_mem:** e.g. 4–16 MB for sorts/joins.
- **max_connections:** Set on Postgres; PgBouncer `pool_size` should be ≤ Postgres `max_connections` (leave headroom for admin and replication).

Defaults in the Postgres image are fine for pilot; for production, tune based on host RAM and workload.

### Backup

- **Logical backup:** `pg_dump -U agentic_rag -d agentic_rag -Fc -f backup.dump` (from host: use port 5433).
- **Restore:** `pg_restore -U agentic_rag -d agentic_rag -c backup.dump` (or create empty DB then restore).
- **Cron:** Schedule `pg_dump` (or use your cloud/managed backup). See runbook below.

---

## 5.4 Qdrant: Sizing and Tuning

### Sizing

- **Single node:** Fine for millions of vectors (768 dim) with enough RAM. Rough guide: ~1–2 GB RAM per 1M vectors (depends on HNSW and payload).
- **Collections:** `section_embeddings` and `chunk_embeddings`; filter every search by `tenant_id`. No need for one collection per tenant unless you want hard isolation.

### Tuning (reference)

- **indexing_threshold:** Number of points before building HNSW index (default 20000). Larger = less rebuilds, slower first queries.
- **hnsw_config:** `m`, `ef_construct` (build), `ef` (search). Higher `ef` = better recall, slower search.
- Our client uses default `VectorParams(size=768, distance=COSINE)`. For very large collections, consider tuning via Qdrant API or config file.

### Backup

- **Snapshot API:** `POST /collections/{name}/snapshots` creates a snapshot; stored under Qdrant’s storage path.
- **File backup:** Backup the volume or directory Qdrant uses (e.g. `qdrant_data` in Docker). Restore by placing files and restarting Qdrant.
- **Recovery:** Point Qdrant at the restored data directory and start. See runbook below.

---

## 5.5 Runbooks

See **docs/runbooks/**:

- **[add-capacity.md](runbooks/add-capacity.md)** — Scale API replicas, add Celery workers, add Postgres/Qdrant resources.
- **[backup-restore.md](runbooks/backup-restore.md)** — Postgres and Qdrant backup and restore steps.
- **[failover.md](runbooks/failover.md)** — What to do if Postgres, Qdrant, or Redis is down (restart, restore, failover).

---

## 5.6 Deliverables Checklist

- [x] PgBouncer service in Docker; API and Celery connect via PgBouncer.
- [x] Document Postgres tuning and backup/restore (this doc + runbooks).
- [x] Document Qdrant sizing, tuning, and backup/restore (this doc + runbooks).
- [x] Runbooks: add capacity, backup-restore, failover.
- [x] Phase 5 validation: script to verify stack with PgBouncer (health, search, tenant isolation).

---

## 5.7 Configuration Summary

| Component | Without Phase 5 (direct) | With Phase 5 (Docker) |
|-----------|---------------------------|------------------------|
| API/Celery → Postgres | postgres:5432 | pgbouncer:6432 |
| Host scripts → Postgres | localhost:5433 | localhost:5433 (unchanged) |
| Qdrant | qdrant:6333 | qdrant:6333 (unchanged) |
