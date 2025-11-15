# Phase 3: Async Ingestion (Celery + Redis) — Plan and Specification

Upload and ingestion run in the background so the API returns immediately with a job ID; clients can poll for status.

---

## 1. Goals

- **Non-blocking upload:** Upload API can return `202 Accepted` with `job_id`; ingestion runs in a Celery worker.
- **Job status:** Store status in Redis; optional `GET /ingest/status/{job_id}` for polling.
- **Same pipeline:** Workers use the same `IngestionPipeline` (async run via `asyncio.run`), same Postgres/Qdrant/embedding config.

---

## 2. Execution Plan

| # | Task | Description |
|---|------|-------------|
| 1 | **Celery app** | Create Celery app with Redis broker (reuse `REDIS_*` / `redis_url`). |
| 2 | **ingest_document_task** | Task args: `job_id`, `tenant_id`, `raw_text`, `title`, `author`, `edition_name`, `publication_year`. On start: set status `running` in Redis. Run ingestion in `asyncio.run()`. On success: set `completed` + sections_count. On failure: set `failed` + error. |
| 3 | **Job status in Redis** | Key `ingest:job:{job_id}`: JSON `{status, created_at, updated_at, result?, error?}`. TTL e.g. 24h. |
| 4 | **Upload API** | Query param or form `async=1`: enqueue task, return `202` with `job_id`. Otherwise keep current sync behavior (200 + sections_count). |
| 5 | **GET /ingest/status/{job_id}** | Return job status from Redis; 404 if not found. |
| 6 | **Config** | `CELERY_BROKER_URL` (default from `redis_url`); optional `INGEST_ASYNC_DEFAULT=false`. |
| 7 | **Docker** | Add `celery-worker` service; same image as API or dedicated; command `celery -A src.worker.celery_app worker -l info`. |
| 8 | **Docs and validation** | How to run worker; scale workers; validate async upload and status. |

---

## 3. Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `CELERY_BROKER_URL` | (from `redis_url`) | Redis URL for Celery broker. |
| `INGEST_JOB_STATUS_TTL_SECONDS` | 86400 | TTL for job status key in Redis (24h). |
| `INGEST_ASYNC_DEFAULT` | false | If true, upload defaults to async (202) unless `async=0`. |

---

## 4. API Contract

- **POST /upload/document**  
  - With `async=1` (query or form): enqueue `ingest_document_task`, return **202 Accepted** with `{"job_id": "...", "message": "Ingestion started. Poll GET /ingest/status/{job_id}."}`.  
  - Without async: current behavior (200, sync ingestion, sections_count).
- **GET /ingest/status/{job_id}**  
  - **200:** `{"job_id", "status": "pending|running|completed|failed", "created_at", "updated_at", "result?", "error?"}`.  
  - **404:** Job not found or expired.

---

## 5. Files to Add/Touch

- `src/worker/__init__.py`
- `src/worker/celery_app.py` — Celery app, `ingest_document_task`.
- `src/worker/ingest_runner.py` — Async runner called from task (asyncio.run).
- `src/api/routes/upload.py` — Optional async path; enqueue task, return 202.
- `src/api/routes/ingest.py` — New router: `GET /ingest/status/{job_id}`.
- `config/settings.py` — Celery broker URL, job TTL.
- `docker-compose.yml` — celery-worker service.
- `docs/PHASE3_ASYNC_INGESTION.md` — This file.
- `.env.example` — Phase 3 vars.
- `tests/test_phase3_async_ingest.py` — Unit/mock tests.
- `scripts/validate_phase3_live.py` — Live validation (optional).

---

## 6. Running the worker

- **Local:** Start Redis (and Postgres/Qdrant if not already). Then:
  ```bash
  celery -A src.worker.celery_app worker -l info
  ```
- **Docker:** The `celery-worker` service uses the same image as the API. Start it with:
  ```bash
  docker compose up -d celery-worker
  ```
  Or start the full stack including the worker: `docker compose up -d`.

---

## 7. Validation

- **Sync upload (default):** `POST /upload/document` without `async_mode` returns 200 and sections_count.
- **Async upload:** `POST /upload/document` with form field `async_mode=1` returns **202** with `job_id` and `status_url`. Poll `GET /ingest/status/{job_id}` until `status` is `completed` or `failed`.
- **Status 404:** Requesting a non-existent or expired job_id returns 404.
