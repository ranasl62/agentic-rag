# How to Run Agentic RAG

This guide gets the application running on your machine. You can use Docker for a full stack or run the API locally against existing services.

---

## Prerequisites

- **Docker and Docker Compose** — for running the full stack (Postgres, Qdrant, Redis, API, optional Nginx and Celery).
- **Python 3.11+** — if you run the API or scripts on the host (we recommend `uv` or `pip`).
- **Ollama** (optional but typical) — for embeddings and chat. Run it on the host or in Docker.

---

## Option A: Run with Docker (recommended)

This is the simplest way to run everything.

### 1. Clone and configure

```bash
git clone https://github.com/your-username/local-ai-agent.git
cd local-ai-agent
cp .env.example .env
```

Edit `.env` and set at least:

- **POSTGRES_PASSWORD** — use a strong password (e.g. `change_me_secure_password` for local dev only).

Other variables have sensible defaults. See [.env.example](../.env.example) for the full list.

### 2. Start the stack

```bash
docker compose up -d
```

This starts:

- **PostgreSQL** (port 5433 on host)
- **Qdrant** (6333)
- **Redis** (6379)
- **PgBouncer** (connection pool for Postgres)
- **Nginx** (API on port **8080**)
- **RAG API** (behind Nginx)
- **Celery worker** (async ingestion)
- **Next.js web UI** (port 3001)

The API is available at **http://localhost:8080**. The interactive API docs (Swagger) are at **http://localhost:8080/docs**.

### 3. Ollama (embeddings and chat)

The API needs an embedding model and a chat model. You can run Ollama on the host or in Docker.

**On the host (typical):**

1. Install and start Ollama (e.g. `ollama serve`).
2. In `.env`, leave `OLLAMA_HOST` as `http://host.docker.internal` (or the default) so the API in Docker can reach it.
3. Pull the models:

   ```bash
   ollama pull nomic-embed-text
   ollama pull llama3.2
   ```

**In Docker:**

```bash
docker compose --profile with-ollama up -d
```

Then set in `.env`: `OLLAMA_HOST=http://ollama`. Pull models inside the container:

```bash
docker compose exec ollama ollama pull nomic-embed-text
docker compose exec ollama ollama pull llama3.2
```

### 4. Create a tenant and API key (when auth is on)

If `REQUIRE_AUTH=true` (default), you need an API key for protected endpoints:

```bash
POSTGRES_HOST=localhost POSTGRES_PORT=5433 uv run python -m scripts.create_tenant "My Tenant" my-tenant
```

Use the printed API key in the `X-API-Key` header for all requests. For local dev you can set `REQUIRE_AUTH=false` in `.env` and restart the API to skip the key.

### 5. Upload a document and query

- **Upload:** Use the Swagger UI at http://localhost:8080/docs → **POST /upload/document**, or see [User guide](USER_GUIDE.md).
- **Search:** `POST /search` with `{"query": "your question", "limit": 10}`.
- **Full pipeline:** `POST /query` with `{"query": "Compare chapter 1 between editions"}`.

---

## Option B: Run the API locally (no Docker for the app)

Use this when you want to develop or debug the API on your machine while using Docker only for dependencies.

### 1. Start dependencies

```bash
docker compose up -d postgres qdrant redis
```

Ensure `.env` points at these (e.g. `POSTGRES_HOST=localhost`, `POSTGRES_PORT=5433`, `QDRANT_HOST=localhost`, `REDIS_HOST=localhost`). If Postgres is exposed on 5433, use that port in `.env`.

### 2. Install Python dependencies

```bash
uv sync
# or: pip install -e ".[dev]"
```

### 3. Run the API

```bash
uv run uvicorn src.api.main:app --host 0.0.0.0 --port 8000
```

The API will be at **http://localhost:8000**. Open **http://localhost:8000/docs** for Swagger. The API will create tables and a default tenant on startup.

### 4. Ollama

Run Ollama on the host (e.g. `ollama serve`) and set in `.env`:

- `OLLAMA_HOST=http://localhost`
- `OLLAMA_PORT=11434`

Pull the same models as above (`nomic-embed-text`, `llama3.2`).

---

## Environment at a glance

| Variable | Purpose | Default |
|----------|---------|---------|
| **POSTGRES_*** | Database connection | localhost:5432 (use 5433 if Docker publishes that) |
| **QDRANT_*** | Vector store | localhost:6333 |
| **REDIS_*** | Cache, rate limit, Celery broker | localhost:6379 |
| **OLLAMA_HOST** | Where the API finds Ollama | http://localhost (host) or http://ollama (Docker) |
| **OLLAMA_EMBED_MODEL** | Embedding model | nomic-embed-text |
| **OLLAMA_CHAT_MODEL** | Default chat model | llama3.2 |
| **REQUIRE_AUTH** | Require X-API-Key | true |
| **API_PORT** | Port the API listens on | 8080 (with Nginx) or 8000 (standalone) |

For chat and embeddings you can switch to OpenAI or Anthropic; see [Models and observability](MODELS_AND_OBSERVABILITY.md).

---

## Troubleshooting

- **API won’t start:** Check that Postgres, Qdrant, and Redis are reachable (host/port in `.env`). If you use Docker for DBs, use the host port (e.g. 5433 for Postgres).
- **“Connection refused” to Ollama:** Ensure Ollama is running and `OLLAMA_HOST`/`OLLAMA_PORT` match. From inside a container use `http://host.docker.internal` for the host.
- **401 on requests:** When `REQUIRE_AUTH=true`, send a valid `X-API-Key` or create a tenant with `scripts/create_tenant.py`.
- **Empty search results:** Confirm you’ve uploaded documents for the tenant whose API key you’re using, and that the embedding model matches the one used at ingestion time.

For more detail, see [Developer guide](DEVELOPER_GUIDE.md) and [Operations](OPERATIONS.md).
