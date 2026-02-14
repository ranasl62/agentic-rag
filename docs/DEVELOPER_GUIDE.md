# Developer Guide

How to set up the project, navigate the codebase, and extend the RAG system (new tools, agents, or features). For system design, see [Architecture & design](ARCHITECTURE_AND_DESIGN.md). For running and testing, see [Testing guide](TESTING_GUIDE.md).

---

## Prerequisites

- **Python 3.11+** (recommended: use `uv` for installs and runs)
- **Docker & Docker Compose** for full stack (Postgres, Qdrant, Redis, Nginx, etc.)
- **Ollama** (or OpenAI/Anthropic) for embeddings and LLM

---

## Repository layout

```
config/           # Settings from env (config/settings.py)
src/
  api/            # FastAPI app, auth, rate limit, cache, metrics, routes
  agents/         # Orchestrator and agents (query, retrieval, comparison, etc.)
  tools/          # Tools invoked by orchestrator (search, match, compare, summarize)
  storage/        # Postgres, Qdrant, Redis clients and models
  ingestion/      # Pipeline, structure extraction, chunking, section IDs
  llm/            # Embeddings and chat client (Ollama/OpenAI/Anthropic)
  worker/         # Celery app and async ingest task
  utils/          # Logging, text helpers
scripts/          # CLI: create_tenant, ingest_book, chat, validate_phase*_live
tests/            # Unit and integration tests per phase
docker/           # Dockerfiles, nginx.conf
docs/             # All documentation
```

---

## Local setup

### 1. Clone and install

```bash
cd local-ai-agent
uv sync   # or: pip install -e ".[dev]"
```

### 2. Environment

```bash
cp .env.example .env
# Edit .env: at least POSTGRES_PASSWORD; set REQUIRE_AUTH=false for local dev if you prefer.
```

Key variables for development:

- **POSTGRES_***, **QDRANT_***, **REDIS_*** — storage (use defaults if running via Docker).
- **OLLAMA_HOST** — e.g. `http://localhost:11434` (host) or `http://ollama` (Ollama in Docker).
- **REQUIRE_AUTH** — `false` to call API without API key (default tenant).
- **API_PORT** — 8000 when running API alone; 8080 when behind Nginx in Docker.

### 3. Run dependencies (Docker)

```bash
docker compose up -d postgres qdrant redis
# Optional: pgbouncer, nginx, celery-worker, web
```

Or run Postgres, Qdrant, and Redis however you prefer; point `.env` at their hosts/ports.

### 4. Run the API

```bash
uv run uvicorn src.api.main:app --host 0.0.0.0 --port 8000
```

API: http://localhost:8000 — docs at http://localhost:8000/docs.

### 5. Create DB and tenant (if using auth)

```bash
# Tables are created at API startup; optionally:
uv run python -m scripts.setup_db

# Create a tenant and get an API key:
POSTGRES_HOST=localhost POSTGRES_PORT=5433 uv run python -m scripts.create_tenant "Dev Tenant" dev
```

---

## Key concepts for developers

- **Tenant**: Every request is bound to a tenant (from API key or default). All book/section/upload and search operations are scoped by `tenant_id`.
- **Book / Edition / Section**: A *book* has metadata (title, author). An *edition* is one version (e.g. "2015", "2021"). *Sections* belong to an edition and have a stable `canonical_section_id` for matching across editions.
- **Orchestrator**: The single entry for “natural language query”. It runs: Query Understanding → Retrieval Planning → Tool execution → Comparison/Summarization → optional Verification.
- **Tools**: Stateless functions called by the orchestrator. They take structured params, use storage (Postgres, Qdrant) and optionally LLM, and return structured results. All tools receive `tenant_id`.
- **Agents**: LLM-based components that produce structured output (intent, plan, summary). They do not call each other; the orchestrator calls them and then calls tools.

---

## Extending the system

### Adding a new tool

1. **Implement the tool** in `src/tools/` (e.g. a new file or add to an existing one). Follow the pattern of `base_tool.py` / existing tools: clear input/output schema, use `tenant_id` for any storage access.
2. **Register** the tool so the orchestrator (or retrieval planning agent) knows about it. This usually means adding it to the list of tools passed to the retrieval planner and implementing the execution branch in the orchestrator.
3. **Update prompts** in `src/agents/` (e.g. retrieval_planning_agent) so the LLM knows when to call the new tool and with what parameters.
4. **Add tests** in `tests/` (unit test for the tool; optionally integration for the full pipeline).

### Adding or changing an agent

- Agents live in `src/agents/`. Each has a clear responsibility and returns structured data (e.g. Pydantic models).
- To add an agent: implement it, then call it from the orchestrator in the appropriate step (e.g. after retrieval planning, before comparison).
- To change behavior: adjust the agent’s prompt in `src/llm/prompt_templates.py` or in the agent module, and optionally add or tweak tools it can request.

### Adding a new API endpoint

- Add a route in the appropriate router under `src/api/routes/` (or create a new router and include it in `src/api/main.py`).
- Use `get_current_tenant()` and `rate_limit_dependency()` if the endpoint should be tenant-scoped and rate-limited.
- Document the endpoint (docstring and tags) for OpenAPI.

### Supporting another document format

- Parsing: add a parser that produces raw text (and optionally structure) in `src/ingestion/` and plug it into the ingestion pipeline. PDF is already handled (text extraction then same path as TXT).
- Metadata: if you need new fields (e.g. language, country), extend the storage models and Qdrant payloads, and the upload API, as needed.

---

## Config and env

- **Single source of truth**: `config/settings.py` loads from environment (and `.env`). Use `get_settings()` in code.
- **.env.example** lists all supported variables with short comments (Phases 1–6, auth, rate limit, cache, async ingest, metrics, etc.). Copy to `.env` and override.

---

## Coding conventions

- **Async**: API and tools are async where I/O is involved; use `async`/`await` consistently.
- **Types**: Use type hints and Pydantic for request/response and agent outputs.
- **Tenant**: Never bypass tenant isolation; all DB and Qdrant queries that touch user data must filter by `tenant_id`.
- **Errors**: Use HTTPException for API errors; return clear error messages for clients.

---

## Where to look for …

| Goal | Where |
|------|--------|
| Change how queries are interpreted | `src/agents/query_understanding_agent.py`, prompts |
| Change how retrieval is planned | `src/agents/retrieval_planning_agent.py`, tools list |
| Add or change search behavior | `src/tools/search_tools.py`, `src/storage/qdrant_client.py` |
| Change comparison/summary output | `src/agents/comparison_agent.py`, `src/agents/summarization_agent.py` |
| Change ingestion structure | `src/ingestion/parsers/structure_extractor.py`, `src/ingestion/chunking/` |
| Add or change API routes | `src/api/routes/`, `src/api/main.py` |
| Auth or rate limits | `src/api/auth.py`, `src/api/rate_limit.py` |

For full testing (unit, live, E2E), see [Testing guide](TESTING_GUIDE.md).
