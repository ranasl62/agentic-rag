# Runbook: Add Capacity

How to scale API replicas, Celery workers, and when to add resources for Postgres/Qdrant.

---

## 1. Scale API replicas (Phase 4)

More API instances behind Nginx to handle more concurrent requests.

```bash
# Scale to 2 or 3 API replicas
docker compose up -d --scale api-service=2
```

- Traffic is load-balanced by Nginx across replicas.
- Ensure PgBouncer is in place (Phase 5) so many replicas don’t exhaust Postgres connections.

---

## 2. Add Celery workers (ingestion)

More workers to process more uploads in parallel.

```bash
# Run a second worker (same image, same queue)
docker compose up -d --scale celery-worker=2
```

- All workers consume from the same Redis/Celery queue.
- Each worker needs Postgres and Qdrant access (via PgBouncer and Qdrant in Docker).

---

## 3. Postgres: when to add capacity

- **Symptoms:** High CPU, slow queries, or connection errors (e.g. “too many connections” if not using PgBouncer).
- **Actions:**
  - Ensure **PgBouncer** is used (Phase 5) so connection count stays bounded.
  - **Tune:** Increase `shared_buffers`, `work_mem` (see docs/PHASE5_QDRANT_POSTGRES_SCALING.md).
  - **Vertical:** Larger instance/container for Postgres.
  - **Read replicas (optional):** Add a read replica and route read-only queries (list books, get section) to it; keep writes on primary. Requires app/config changes to support two connection targets.

---

## 4. Qdrant: when to add capacity

- **Symptoms:** High memory, slow search, or OOM.
- **Actions:**
  - **Single node:** Increase RAM/disk; tune HNSW (e.g. `ef`, `indexing_threshold`) if needed.
  - **Cluster:** For very large vector counts or HA, consider Qdrant cluster (replication/sharding). See Qdrant docs.
  - All searches must keep filtering by `tenant_id`; no need for a collection per tenant unless you want hard isolation.

---

## 5. Redis

- Used for rate limiting, cache, and Celery broker. Usually one instance is enough; for HA add Redis Sentinel or a managed Redis.
- If you see memory or connection issues, increase Redis memory or add replicas per your Redis deployment guide.
