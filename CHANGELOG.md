# Changelog

Rough log of what landed. Not always in sync with commits.

## 2026-02

- Testing guide and phase validation docs overhaul. Scripts tolerate empty/non-JSON API responses.
- README doc index and testing section. Default API port 8080 everywhere.
- OpenAPI tags, /info, /health version. Validation scripts default to 8080.

## 2026-01

- Phase 6: Prometheus /metrics, structured request logging (request_id, tenant_id, duration).
- Runbooks: monitoring, add-capacity, backup-restore, failover.
- Phase 5: PgBouncer in compose, API/Celery use it. Qdrant/Postgres sizing docs.
- Phase 4: Nginx in front of API, scale api-service=N.
- Phase 3: Celery async ingest, 202 + job_id, GET /ingest/status.
- Phase 2: Redis rate limiting (per-tenant), search/query cache, skip_cache.
- Phase 1: Tenants, API key auth, tenant_id everywhere, create_tenant + backfill scripts.

## 2025-12

- Full RAG pipeline: query understanding → retrieval planning → tools → compare/summarize → verification.
- Upload document (sync + async), ingest_book CLI. Postgres + Qdrant + Redis.
- Agents and tools (search_sections, compare_sections, summarize_section, etc.).

## 2025-11

- Project scaffold: ingestion pipeline (structure extractor, semantic chunking), embeddings (Ollama), storage (Postgres + Qdrant).
- FastAPI skeleton: /health, /books, /search. Basic compare and summarize stubs.
