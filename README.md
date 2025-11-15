# Agentic RAG — Multi-Edition Document Analysis

Local-first RAG: drop in PDFs or TXT (books, manuals, reports—anything), search by meaning, compare the same section across editions, and get summaries with citations. We built it to scale (multi-tenant, rate limits, cache, async ingest, Nginx, metrics). See [Overview & scope](docs/OVERVIEW_AND_SCOPE.md) for what it does and what you can feed it.

---

## Features

- **Ingestion:** Parse books into book → edition → chapter → section; stable `canonical_section_id`; semantic chunking; embed with Ollama (or OpenAI); store in Postgres + Qdrant.
- **Vector store:** Qdrant with metadata filtering; section and chunk search; same-section-across-editions and cross-book search.
- **Agents & tools:** Query Understanding, Retrieval Planning, Section Matching, Comparison, Summarization, Verification. Tools: `search_sections`, `find_same_section_across_editions`, `compare_sections`, `summarize_section`, `list_available_editions`, and more. Strict schemas, testable.
- **API:** FastAPI — `/search`, `/compare`, `/summarize`, `/books`, `/sections`, `/query` (full pipeline), `/upload/document`, `/ingest/status`, `/health`, `/metrics` (Prometheus).
- **Production stack (Phases 1–6):** Tenant auth (API key), rate limiting & Redis cache, async ingestion (Celery), Nginx load balancer, PgBouncer, runbooks, Prometheus metrics, structured logging.

---

## Requirements

- Docker and Docker Compose
- (Optional) Ollama on host or in Docker for embeddings and chat

---

## Quick Start

1. **Configure**

   ```bash
   cp .env.example .env
   # Set POSTGRES_PASSWORD (and optionally other vars). See .env.example for Phase 1–6 options.
   ```

2. **Start the stack**

   ```bash
   docker compose up -d
   ```

   This starts **Postgres**, **Qdrant**, **Redis**, **PgBouncer**, **Nginx** (API on port **8080**), **RAG API**, **Celery worker** (optional), and **Next.js web** (default port 3001). The API is reached at **http://localhost:8080** (Nginx). Open the UI at **http://localhost:3001** and the API docs at **http://localhost:8080/docs**.

   **Ollama:** Run on the host (port 11434) or in Docker: `docker compose --profile with-ollama up -d` and set `OLLAMA_HOST=http://ollama`. Then:

   ```bash
   ollama pull nomic-embed-text && ollama pull llama3.2
   ```

3. **Create a tenant and API key** (when using auth)

   ```bash
   POSTGRES_HOST=localhost POSTGRES_PORT=5433 uv run python -m scripts.create_tenant "My Tenant" my-tenant
   # Save the printed API key; use header X-API-Key in requests.
   ```

4. **Ingest or upload**

   - **Upload via API:** `POST /upload/document` (multipart: file, title, author, edition_name). Use `async_mode=1` for async (returns 202 + job_id; poll `GET /ingest/status/{job_id}`).
   - **CLI:** `docker compose run --rm -v $(pwd)/data:/app/data api-service python -m scripts.ingest_book --title "My Book" --author "Author" --edition "2021" --file /app/data/book.txt`

5. **Query**

   - **Search:** `POST /search` with `{"query": "...", "limit": 10}` (header `X-API-Key` if auth enabled).
   - **Full pipeline:** `POST /query` with `{"query": "Compare section X between editions"}`.
   - **Interactive chat:** `API_BASE_URL=http://localhost:8080 AGENT_API_KEY=your-key uv run python -m scripts.chat`

---

## Testing (Phase 1–6)

**Unit tests** (no services required for Phase 2/3/5/6 logic; Phase 1 endpoint tests need Postgres):

```bash
uv run pytest tests/test_phase1_validation.py tests/test_phase2_rate_limit_cache.py \
  tests/test_phase3_async_ingest.py tests/test_phase5_pgbouncer.py \
  tests/test_phase6_metrics.py tests/test_phase6_logging.py -v --tb=short
```

**Live validation** (API + stack at **http://localhost:8080**):

```bash
export API_BASE_URL=http://localhost:8080
uv run python -m scripts.validate_phase1_live   # Auth & tenant isolation
uv run python -m scripts.validate_phase2_live   # Rate limit & cache
uv run python -m scripts.validate_phase3_live   # Async ingestion
uv run python -m scripts.validate_phase4_live   # LB & scaling
uv run python -m scripts.validate_phase5_live   # PgBouncer & stack
uv run python -m scripts.validate_phase6_live   # Metrics
```

Full testing guide (unit + live + E2E + status): **[docs/TESTING_GUIDE.md](docs/TESTING_GUIDE.md)**.

---

## Project structure

| Path | Purpose |
|------|--------|
| `config/` | Settings (env); Postgres, Qdrant, Redis, Ollama, auth, rate limit, cache, Phase 3–6. |
| `src/api/` | FastAPI app, auth, rate limit, cache, metrics, middleware, routes (search, compare, summarize, books, upload, ingest, debug). |
| `src/worker/` | Celery app and async ingest task (Phase 3). |
| `src/storage/` | Postgres and Qdrant clients; Redis. |
| `src/llm/`, `src/agents/`, `src/tools/` | Embeddings, chat, agents, tools. |
| `src/ingestion/` | Pipeline, chunking, vehicle_metadata (design). |
| `scripts/` | create_tenant, backfill_tenant, ingest_book, chat, validate_phase*_live. |
| `docker/` | Dockerfiles; nginx.conf (Phase 4); PgBouncer via Bitnami in compose. |
| `docs/` | Architecture, API reference, user guide, **PRODUCTION_ROADMAP_60K.md** (Phases 1–6), phase specs, runbooks. |

---

## Documentation

Full documentation is split into separate pages and linked below. Start with [Overview & scope](docs/OVERVIEW_AND_SCOPE.md) to understand what the system does and what kind of documents it supports (any PDF/TXT—books, manuals, reports, articles—not limited to repair manuals). **Full index:** [docs/README.md](docs/README.md).

| Page | Description |
|------|-------------|
| **[Overview & scope](docs/OVERVIEW_AND_SCOPE.md)** | What problem we solve, scope (any document type), capabilities, and who the docs are for. |
| **[User guide](docs/USER_GUIDE.md)** | Upload documents, search, compare two editions, summarize. For end users. |
| **[Architecture & design](docs/ARCHITECTURE_AND_DESIGN.md)** | How the RAG system is built: components, data flow, design decisions, production stack. |
| **[Developer guide](docs/DEVELOPER_GUIDE.md)** | Code layout, local setup, config, how to extend (tools, agents, endpoints). |
| **[Testing guide](docs/TESTING_GUIDE.md)** | How to test the **whole** application: unit tests, live validation scripts, E2E flow (upload → search → compare), manual testing. |
| **[API reference](docs/api_reference.md)** | Base URL, auth, and curl examples for main endpoints. |
| **[Production roadmap](docs/PRODUCTION_ROADMAP_60K.md)** | Phases 1–6: auth, rate limit, cache, async ingest, scaling, monitoring. |
| **[Runbooks](docs/runbooks/)** | add-capacity, backup-restore, failover, monitoring. |
| **[Phase alignment](docs/PHASE1_PHASE6_ALIGNMENT.md)** | How phases map to docs, scripts, and tests. |

Other docs: [Phase 1 auth](docs/PHASE1_AUTH_TENANTS.md), [Phase 2 rate limit & cache](docs/PHASE2_RATE_LIMIT_CACHE.md), [Phase 3 async ingest](docs/PHASE3_ASYNC_INGESTION.md), [Phase 4 API scaling](docs/PHASE4_API_SCALING.md), [Phase 5 Qdrant/Postgres](docs/PHASE5_QDRANT_POSTGRES_SCALING.md), [Phase 6 monitoring](docs/PHASE6_MONITORING_ALERTS.md), [agent prompts](docs/agent_prompts.md), [models & observability](docs/MODELS_AND_OBSERVABILITY.md), [document scope & vehicle metadata](docs/DOCUMENT_SCOPE_AND_VEHICLE_METADATA.md).

---

## Design

- **Local-first:** Ollama (or OpenAI) for LLM/embeddings; Qdrant; Postgres; Redis. No vendor lock-in for core RAG.
- **Tenant isolation:** Every request is scoped to a tenant (API key); data and search are per-tenant.
- **Tool-based agents:** Each agent has a single responsibility; orchestrator invokes tools explicitly; citations and verification supported.
- **Stateless API:** Auth and cache are per-request or shared (Redis/DB); run multiple replicas behind Nginx.

---

## License

Use as needed for internal research, legal/academic comparison, or knowledge analysis.
