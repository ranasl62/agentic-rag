# Agentic RAG — Multi-Edition Document Analysis

Local-first RAG: ingest PDFs or plain text (books, manuals, reports—any domain), search by meaning, compare the same section across editions, and get summaries with citations. Built for production: multi-tenant auth, rate limiting, caching, async ingestion, and horizontal scaling.

---

## How to run

The fastest way is with Docker. You need a `.env` file (copy from `.env.example`) and at least `POSTGRES_PASSWORD` set.

```bash
cp .env.example .env
# Edit .env: set POSTGRES_PASSWORD
docker compose up -d
```

The API is at **http://localhost:8080** (Swagger at **http://localhost:8080/docs**). **Before installing Ollama:** see [Getting started](docs/GETTING_STARTED.md) — you can use **OpenAI or Anthropic only** and skip Ollama; only install Ollama if you want local models. Full steps, local development, and troubleshooting: **[docs/GETTING_STARTED.md](docs/GETTING_STARTED.md)**.

---

## Documentation

| Topic | Document |
|-------|----------|
| **How to run** | [Getting started](docs/GETTING_STARTED.md) — Docker and local run, env, Ollama, troubleshooting |
| **Tools & stack** | [Tech stack](docs/TECH_STACK.md) — Python, FastAPI, Postgres, Qdrant, Redis, Ollama, Celery, Nginx |
| **Models** | [Models and observability](docs/MODELS_AND_OBSERVABILITY.md) — Ollama, OpenAI, Anthropic; per-task models |
| **API** | [API reference](docs/api_reference.md) — All endpoints, auth, request/response, examples |
| **Features** | [Features](docs/FEATURES.md) — Ingestion, search, compare, summarize, agents, auth, scaling |

| For | Docs |
|-----|------|
| **Getting started** | [Overview & scope](docs/OVERVIEW_AND_SCOPE.md) · [User guide](docs/USER_GUIDE.md) |
| **Developers** | [Architecture & design](docs/ARCHITECTURE_AND_DESIGN.md) · [Developer guide](docs/DEVELOPER_GUIDE.md) · [Testing guide](docs/TESTING_GUIDE.md) |
| **Production** | [Deployment](docs/DEPLOYMENT.md) · [Operations](docs/OPERATIONS.md) |

Full index: [docs/README.md](docs/README.md).

---

## Features (summary)

- **Ingestion:** PDF and TXT → structure (book/edition/chapter/section) → semantic chunking → embeddings (Ollama or OpenAI) → Postgres + Qdrant. Sync or async (Celery).
- **Search:** Semantic search over sections; filter by tenant, book, edition; optional LLM-generated answer; cache and rate limits.
- **Compare & summarize:** Same section across editions; summarize one or more sections or run a natural-language summary via the agent pipeline.
- **Agentic query:** Single natural-language question → query understanding → retrieval plan → tools (search, match, compare, summarize) → verification. Citations included.
- **Production:** Tenant auth (API key), per-tenant rate limits, Redis cache, Nginx LB, PgBouncer, Prometheus metrics, structured logging.

Details: [Features](docs/FEATURES.md).

---

## Quick start

1. **Configure**

   ```bash
   cp .env.example .env
   # Set POSTGRES_PASSWORD (and optionally other vars). See .env.example for Phase 1–6 options.
   ```

2. **Start the stack**

   ```bash
   docker compose up -d
   ```

   This starts **Postgres**, **Qdrant**, **Redis**, **PgBouncer**, **Nginx** (API on port **8080**), **RAG API**, **Celery worker**, and **Next.js web** (port **3002**). The API is at **http://localhost:8080** (Nginx). Open the UI at **http://localhost:3002** and the API docs at **http://localhost:8080/docs**.

   **Ollama (optional):** Only if you want local models — run on the host (port 11434) or in Docker: `docker compose --profile with-ollama up -d` and set `OLLAMA_HOST=http://ollama`. Then pull `nomic-embed-text` and `llama3.2`. To use **OpenAI/Anthropic only**, set `CHAT_PROVIDER` and `EMBED_PROVIDER` in `.env` and skip Ollama; see [Getting started](docs/GETTING_STARTED.md).

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
| `docs/` | Getting started, tech stack, models, API reference, features, user guide, deployment, operations. |

---

## Contributing and license

Contributions are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) for setup, testing, and how to send patches.

This project is licensed under the **MIT License** — see [LICENSE](LICENSE). You can use, copy, modify, and distribute it for any purpose, including commercial use.

---

## Design

- **Local-first:** Ollama (or OpenAI) for LLM/embeddings; Qdrant; Postgres; Redis. No vendor lock-in for core RAG.
- **Tenant isolation:** Every request is scoped to a tenant (API key); data and search are per-tenant.
- **Tool-based agents:** Each agent has a single responsibility; orchestrator invokes tools explicitly; citations and verification supported.
- **Stateless API:** Auth and cache are per-request or shared (Redis/DB); run multiple replicas behind Nginx.

---

