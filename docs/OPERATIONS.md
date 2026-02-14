# Operations Guide

Runbooks for running the Agentic RAG stack in production: scaling, backup and restore, failover, and monitoring.

---

## 1. Adding capacity

### Scale API replicas

More API instances behind Nginx for higher concurrency:

```bash
docker compose up -d --scale api-service=2
```

Use PgBouncer so many replicas do not exhaust Postgres connections.

### Scale Celery workers

More workers to process uploads in parallel:

```bash
docker compose up -d --scale celery-worker=2
```

Workers share the same Redis/Celery queue.

### Postgres

- **Symptoms:** High CPU, slow queries, "too many connections."
- **Actions:** Use PgBouncer; tune `shared_buffers`, `work_mem`; vertical scaling; optional read replicas for read-heavy workloads.

### Qdrant

- **Symptoms:** High memory, slow search, OOM.
- **Actions:** Increase RAM/disk; tune HNSW; for very large datasets consider Qdrant cluster (see Qdrant docs).

### Redis

Used for rate limiting, cache, and Celery broker. One instance is usually enough; for HA use Redis Sentinel or managed Redis.

---

## 2. Backup and restore

### Postgres (logical backup)

From the host (Postgres on port 5433):

```bash
export PGPASSWORD="${POSTGRES_PASSWORD}"
pg_dump -h localhost -p 5433 -U agentic_rag -d agentic_rag -Fc -f agentic_rag_$(date +%Y%m%d).dump
```

Restore (e.g. after recreating DB):

```bash
pg_restore -h localhost -p 5433 -U agentic_rag -d agentic_rag -c agentic_rag_YYYYMMDD.dump
```

Then restart API and Celery.

### Qdrant

- **Snapshot (per collection):** `POST http://localhost:6333/collections/section_embeddings/snapshots` (and same for `chunk_embeddings`). Snapshots live in Qdrant’s data path.
- **Volume backup:** Back up the Qdrant data volume (e.g. Docker volume); restore by replacing the volume and restarting Qdrant.

---

## 3. Failover and recovery

| Component   | Symptoms                    | Actions |
|------------|-----------------------------|--------|
| **Postgres** | Connection refused, 503     | `docker compose restart postgres`; if corrupted, restore from backup; then restart API and Celery. |
| **PgBouncer** | API/Celery can’t reach DB  | Restart PgBouncer; ensure Postgres is up first; restart API and Celery. |
| **Qdrant** | Search fails, 503           | Restart Qdrant; if corrupted, restore from snapshot/volume; restart API and Celery. |
| **Redis**  | Rate limit/cache/Celery fail | Restart Redis; restart Celery; API reconnects on next request. |
| **API / Nginx** | 502/503, connection refused | Restart `api-service` and `nginx`; if scaled, `docker compose up -d --scale api-service=2`. |

### Debug “no search results”

- Verify tenant: client must send the correct API key (tenant).
- Check Qdrant has data: use `GET /debug/vector-status` (with API key).
- Ensure embedding model and dimensions match ingestion.

---

## 4. Monitoring

### Metrics (Prometheus)

The API exposes **GET /metrics** (no auth) in Prometheus text format.

| Metric | Type | Description |
|--------|------|-------------|
| `http_requests_total` | Counter | Labels: method, endpoint, status_class (2xx, 4xx, 5xx) |
| `http_request_duration_seconds` | Histogram | Request latency by endpoint |

Set `METRICS_ENABLED=true` (default). Scrape `http://api-host:8080/metrics` (or your API port).

### Suggested alerts

- **High 5xx rate:** e.g. `sum(rate(http_requests_total{status_class="5xx"}[5m])) / sum(rate(http_requests_total[5m])) > 0.05`.
- **High latency:** e.g. p95 > 10s.
- **API down:** `up{job="agentic-rag-api"} == 0`.

### Grafana

- Request rate by endpoint; error rate; latency p50/p95/p99; top endpoints by volume.

### Logging

Each request is logged as JSON with `request_id`, `tenant_id`, `method`, `path`, `endpoint`, `status_code`, `duration_ms`. Set `LOG_LEVEL` via env; ship logs to your aggregator (e.g. Loki, Elasticsearch).
