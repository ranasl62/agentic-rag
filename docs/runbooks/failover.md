# Runbook: Failover and Recovery

What to do when Postgres, Qdrant, Redis, or the API is down.

---

## 1. Postgres down

- **Symptoms:** API and Celery errors: “connection refused”, “could not connect to server”, 503s.
- **Actions:**
  1. Check Postgres container: `docker compose ps postgres`; `docker compose logs postgres`.
  2. Restart: `docker compose restart postgres`. Wait for health (pg_isready).
  3. If data is corrupted or lost, restore from the latest backup (see [backup-restore.md](backup-restore.md)).
  4. Restart API and Celery so they reconnect: `docker compose restart api-service celery-worker`.

---

## 2. PgBouncer down (Phase 5)

- **Symptoms:** API/Celery can’t connect to Postgres (they connect via PgBouncer).
- **Actions:**
  1. `docker compose ps pgbouncer`; `docker compose logs pgbouncer`.
  2. Restart: `docker compose restart pgbouncer`. Ensure Postgres is healthy first.
  3. Then restart API and Celery if they were failing: `docker compose restart api-service celery-worker`.

---

## 3. Qdrant down

- **Symptoms:** Search and query fail; “connection refused” to Qdrant; 503 from API.
- **Actions:**
  1. `docker compose ps qdrant`; `docker compose logs qdrant`.
  2. Restart: `docker compose restart qdrant`.
  3. If the volume is corrupted, restore from snapshot or file backup (see [backup-restore.md](backup-restore.md)).
  4. Restart API and Celery: `docker compose restart api-service celery-worker`.

---

## 4. Redis down

- **Symptoms:** Rate limiting and cache may fail; Celery tasks don’t run; possible 503 or 500.
- **Actions:**
  1. `docker compose ps redis`; `docker compose logs redis`.
  2. Restart: `docker compose restart redis`.
  3. Restart Celery so workers reconnect: `docker compose restart celery-worker`.
  4. API will reconnect to Redis on next request (rate limit/cache).

---

## 5. API (or Nginx) down

- **Symptoms:** Clients get connection refused or 502/503.
- **Actions:**
  1. `docker compose ps nginx api-service`; `docker compose logs api-service`.
  2. Restart: `docker compose restart api-service` (and `nginx` if needed).
  3. If scaling: `docker compose up -d --scale api-service=2` to bring up replicas.

---

## 6. Debug “no search results”

- **Check:** tenant_id: ensure the client sends the correct API key (tenant). Wrong key → wrong tenant → no data.
- **Check:** Qdrant has data: use GET /debug/vector-status (with API key) to see collection counts and a sample search.
- **Check:** Embedding model matches ingestion (e.g. same Ollama/OpenAI model and dimensions).
