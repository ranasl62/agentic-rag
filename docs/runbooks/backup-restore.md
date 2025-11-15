# Runbook: Backup and Restore

Postgres and Qdrant backup and restore procedures.

---

## 1. Postgres backup

### Logical backup (recommended for portability)

From the **host** (Postgres is on port 5433):

```bash
export PGPASSWORD="${POSTGRES_PASSWORD:-change_me_secure_password}"
pg_dump -h localhost -p 5433 -U agentic_rag -d agentic_rag -Fc -f agentic_rag_$(date +%Y%m%d_%H%M).dump
```

- `-Fc`: custom format (compressed, supports parallel restore).
- Store the `.dump` file somewhere safe (object storage, backup server).

### Automated backups (cron example)

```bash
# Daily at 02:00
0 2 * * * PGPASSWORD='...' pg_dump -h localhost -p 5433 -U agentic_rag -d agentic_rag -Fc -f /backups/agentic_rag_$(date +\%Y\%m\%d).dump
```

---

## 2. Postgres restore

### Restore into existing (empty or replace) database

```bash
export PGPASSWORD="${POSTGRES_PASSWORD:-change_me_secure_password}"
# Drop and recreate if needed (destructive)
psql -h localhost -p 5433 -U agentic_rag -d postgres -c "DROP DATABASE IF EXISTS agentic_rag;"
psql -h localhost -p 5433 -U agentic_rag -d postgres -c "CREATE DATABASE agentic_rag OWNER agentic_rag;"
# Restore
pg_restore -h localhost -p 5433 -U agentic_rag -d agentic_rag -c agentic_rag_YYYYMMDD.dump
```

- `-c`: clean (drop) objects before recreate; use with care.
- After restore, restart API and Celery so they reconnect with a clean schema.

---

## 3. Qdrant backup

### Snapshot via API (per collection)

```bash
# Create snapshot for section_embeddings (requires Qdrant to be reachable)
curl -X POST "http://localhost:6333/collections/section_embeddings/snapshots"
curl -X POST "http://localhost:6333/collections/chunk_embeddings/snapshots"
```

- Snapshots are written under Qdrant’s storage path (e.g. in Docker: volume `qdrant_data`).
- List: `GET /collections/{name}/snapshots`.

### File-level backup (Docker volume)

```bash
# Backup the Qdrant data volume (example: copy to host)
docker run --rm -v local-ai-agent_qdrant_data:/data -v $(pwd)/qdrant_backup:/backup alpine tar czf /backup/qdrant_$(date +%Y%m%d).tar.gz -C /data .
```

- Restore: stop Qdrant, restore the archive into the volume, start Qdrant.

---

## 4. Qdrant restore from snapshot

- Use Qdrant’s recovery from snapshot (see Qdrant docs: recover collection from snapshot).
- Or restore the file-level backup into the Qdrant data directory and restart.

---

## 5. After restore

- Restart API and Celery: `docker compose restart api-service celery-worker`.
- Run a quick smoke test: GET /health, POST /search (with API key), list books.
