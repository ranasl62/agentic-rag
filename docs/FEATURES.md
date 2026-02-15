# Features

A single place to see what Agentic RAG can do. The system is built so you can run it locally or in production, switch models and providers via config, and scale with tenants, rate limits, and async ingestion.

---

## Document ingestion

- **Formats:** PDF and plain text (.txt). PDFs are converted to text, then processed like any other document.
- **Structure:** The pipeline detects chapters and sections from headings and builds a stable structure. Each section gets a **canonical section ID** so the same logical section can be matched across editions.
- **Chunking:** Semantic chunking (paragraph- and sentence-aware) so search and retrieval keep meaning intact.
- **Embeddings:** OpenAI, Ollama, or other providers (configured via `EMBED_PROVIDER`). Stored in Qdrant with **rich payloads**: tenant, book, edition, section IDs plus **book title/author**, **edition name/year**, **chapter title**, **section title** for better display and future filtering.
- **Metadata storage:** Postgres stores books (title, author, isbn, optional **metadata** JSONB), editions (name, year, publisher, optional **metadata** JSONB), and sections with full text and chapter/section structure. Qdrant stores vectors and the same metadata in payloads for search.
- **Sync and async:** Upload can complete synchronously (200) or return immediately with a job id (202); a Celery worker processes async jobs. Poll **GET /ingest/status/{job_id}** for status.
- **Import and metadata:** See [Import and metadata](IMPORT_AND_METADATA.md).

---

## Search and retrieval

- **Semantic search:** Natural-language or keyword queries over all ingested content. Results are ranked by relevance and scoped by tenant (and optionally book or edition).
- **Filtering:** Filter by `document_id` (or `book_id`), `edition_id`, and always by tenant. Qdrant payloads include book/edition/chapter metadata for rich results and future filter options (e.g. by chapter title).
- **Optional answer generation:** Search can return an LLM-generated short answer from the top results (`generate_answer=true`).
- **Caching:** Search results can be cached in Redis per tenant and query (TTL configurable). Use `skip_cache=true` to bypass.

---

## Compare and summarize

- **Compare:** Retrieve the same logical section across one or more editions (by chapter/section numbers or canonical section ID). Returns side-by-side content and optional LLM summary of differences.
- **Summarize:** Summarize a single section, or summarize differences across multiple sections, or ask a natural-language query and get a summary from the agent pipeline.
- **Citations:** Responses include citations (section, edition, book, location) so you can trace answers back to the source.

---

## Agentic query pipeline

- **Single entry point:** **POST /query** accepts a natural-language question and runs the full pipeline: query understanding → retrieval planning → tool execution → comparison or summarization → optional verification.
- **Agents:** Query understanding (intent, entities), retrieval planning (which tools and parameters), section matching, comparison, summarization, and verification (groundedness check). Each agent has a single responsibility; the orchestrator calls them and the tools.
- **Tools:** `search_sections`, `find_same_section_across_editions`, `compare_sections`, `summarize_section`, `summarize_differences`, `list_available_editions`, `match_sections`. Strict input/output schemas; all tenant-scoped.
- **Caching:** Query results can be cached per tenant and query text. Use `skip_cache=true` to force a fresh run.

---

## Multi-tenancy and auth

- **Tenants:** Every book, edition, and section is associated with a tenant. Search, compare, summarize, and query are scoped to the current tenant.
- **API key auth:** Each tenant has an API key (stored as a hash). Send it in the `X-API-Key` header. The API resolves the tenant and attaches it to the request.
- **Optional auth:** You can disable auth for development (`REQUIRE_AUTH=false`); a default tenant is used when the key is missing.
- **Scripts:** `create_tenant` creates a tenant and returns an API key; `backfill_tenant` assigns existing data to a tenant.

---

## Rate limiting and caching

- **Per-tenant rate limits:** Configurable limits per minute for search, query, upload, compare, summarize, and list. Optional global per-IP limit.
- **429 response:** When a limit is exceeded, the API returns 429 with a `Retry-After` header.
- **Redis:** Used for rate-limit counters and for search/query cache. TTLs and enable/disable are set via env.

---

## Async ingestion (Celery)

- **Async upload:** When you upload with `async_mode=1` (or `true`), the API enqueues a Celery task and returns 202 with a `job_id`. The worker runs the same ingestion pipeline (parse, chunk, embed, store) in the background.
- **Job status:** **GET /ingest/status/{job_id}** returns status (pending, completed, failed). Status is stored in Redis with a configurable TTL.
- **Broker:** Redis is the Celery broker. You can run one or more workers; they share the same queue.

---

## Production and scaling

- **Stateless API:** No in-memory session state. Auth and cache are per-request or shared (Redis/DB). You can run multiple API replicas behind a load balancer.
- **Nginx:** Reverse proxy and load balancer in front of the API. Health checks and TLS termination at the proxy are supported.
- **PgBouncer:** Connection pooler for Postgres so many API and worker processes do not exhaust database connections.
- **Horizontal scaling:** Scale API replicas (`--scale api-service=N`) and Celery workers (`--scale celery-worker=N`) via Docker Compose or your orchestrator.

---

## Observability

- **Prometheus metrics:** **GET /metrics** exposes request count and latency histogram in Prometheus text format. Can be disabled with `METRICS_ENABLED=false`.
- **Structured logging:** Each request is logged as JSON with `request_id`, `tenant_id`, method, path, endpoint, status code, and duration. Log level is configurable.
- **Health and info:** **GET /health** and **GET /info** for liveness and basic version/feature flags.

---

## Models and providers

- **Ollama (default):** Local embeddings and chat. No API key. Model names (embed and per-task chat) are set via env; you can change them anytime and restart.
- **OpenAI:** Optional for chat and/or embeddings. Set `CHAT_PROVIDER=openai` or `EMBED_PROVIDER=openai` and provide an API key. If you switch embedding provider, re-ingest (vector dimension may change).
- **Anthropic:** Optional for chat (e.g. Claude). Set `CHAT_PROVIDER=anthropic` and provide an API key.

See [Models and observability](MODELS_AND_OBSERVABILITY.md) for details.

---

## Optional web UI and chat script

- **Next.js web app:** UI for upload, search, compare, summarize, and query. Served on port **3002** (Docker, configurable via `WEB_PORT`) or 3000 (local dev). Configured with `NEXT_PUBLIC_API_URL` pointing at the API.
- **Chat script:** `scripts/chat` is an interactive CLI that sends each message to **POST /query**. Set `API_BASE_URL` and `AGENT_API_KEY` when auth is on.

---

See [Overview & scope](OVERVIEW_AND_SCOPE.md) and [Getting started](GETTING_STARTED.md).
