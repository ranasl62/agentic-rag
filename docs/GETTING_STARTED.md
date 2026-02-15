# How to Run Agentic RAG

This guide gets the application running on your machine. You can use Docker for a full stack or run the API locally against existing services.

---

## First: Do you want to install Ollama?

The API needs a **chat** and **embedding** provider. **Before installing anything**, choose:

- **I want to use OpenAI or Anthropic only (no local Ollama)**  
  → Set `CHAT_PROVIDER=openai` or `anthropic`, `EMBED_PROVIDER=openai`, and add your API keys in `.env`. **You do not need to install Ollama.** Skip every “Ollama” step in this guide.

- **I want to use local Ollama (or Ollama + cloud later)**  
  → Follow the Ollama steps below (install Ollama, pull models). You can still switch to OpenAI/Anthropic later by changing `.env`.

| Choice | What you need | Install Ollama? |
|--------|----------------|-----------------|
| **OpenAI or Anthropic only** | `CHAT_PROVIDER=openai` or `anthropic`, `EMBED_PROVIDER=openai`, API keys in `.env`. | **No** — skip all Ollama steps. |
| **Ollama (local)** | Run Ollama on the host or in Docker; no API key. | **Yes** — see “Ollama” steps below. |

If you are not sure, choose **OpenAI/Anthropic only** to get started without installing Ollama. You can switch to Ollama later by setting `CHAT_PROVIDER=ollama` and `EMBED_PROVIDER=ollama` and then installing Ollama.

---

## Prerequisites

- **Docker and Docker Compose** — for running the full stack (Postgres, Qdrant, Redis, API, optional Nginx and Celery).
- **Python 3.11+** — if you run the API or scripts on the host (we recommend `uv` or `pip`).
- **Ollama** — only if you chose **Ollama (local)** above. Otherwise skip Ollama entirely.

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
- **Next.js web UI** (port 3002, configurable via `WEB_PORT`)

API at **http://localhost:8080** (or the port in `API_PORT`). Web UI at **http://localhost:3002**. Key URLs: [docs README](README.md#key-urls) or [API reference](api_reference.md).

### 3. Ollama (only if you chose “use local Ollama” above)

If you are using **OpenAI/Anthropic only**, skip this step. Otherwise the API needs an embedding model and a chat model. You can run Ollama on the host or in Docker.

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

If `REQUIRE_AUTH=true` (default), you need an API key for protected endpoints. Run the script **inside Docker** so it connects to the right database:

```bash
docker compose run --rm api-service python -m scripts.create_tenant "My Tenant" my-tenant
```

Or from the host (use port 5433, the published Postgres port):

```bash
POSTGRES_PORT=5433 uv run python -m scripts.create_tenant "My Tenant" my-tenant
```

Use the printed API key in the `X-API-Key` header for all requests. To use the key from the **web UI**, set `NEXT_PUBLIC_AGENT_API_KEY=<your key>` in `.env` and rebuild the web container:

```bash
docker compose build --no-cache web && docker compose up -d web --no-deps
```

For local dev you can set `REQUIRE_AUTH=false` in `.env` and restart the API to skip the key entirely.

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

### 4. Ollama (only if you chose “use local Ollama” above)

If you are using **OpenAI/Anthropic only**, skip this step. Otherwise run Ollama on the host (e.g. `ollama serve`) and set in `.env`:

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
| **CHAT_PROVIDER** | Chat LLM provider | ollama (also: openai, anthropic) |
| **EMBED_PROVIDER** | Embedding provider | ollama (also: openai) |
| **OPENAI_API_KEY** | OpenAI key (when provider=openai) | — |
| **REQUIRE_AUTH** | Require X-API-Key | true |
| **API_PORT** | Nginx published port | 8080 |
| **WEB_PORT** | Next.js web UI port | 3002 |

For chat and embeddings you can switch to OpenAI or Anthropic; see [Models and observability](MODELS_AND_OBSERVABILITY.md).

---

## Troubleshooting

- **API won't start:** Check Postgres, Qdrant, Redis are reachable. Run `docker compose logs api-service --tail 80`.
- **Which port?** Docker + Nginx = **8080**. Local API = **8000**.
- **401 "Invalid or missing API key":** Create a tenant: `docker compose run --rm api-service python -m scripts.create_tenant "My Tenant" my-tenant`. For the web UI set `NEXT_PUBLIC_AGENT_API_KEY` in `.env` and rebuild: `docker compose build --no-cache web && docker compose up -d web --no-deps`.
- **`create_tenant` auth failed:** Postgres in Docker publishes on port **5433**. Use `POSTGRES_PORT=5433` or run inside Docker (step 4).
- **CORS errors:** Handled by FastAPI. Nginx must not add duplicate CORS headers.
- **413 on upload:** Increase `client_max_body_size` in `docker/nginx.conf` `/upload/` block.
- **504 timeout on upload:** Documents are processed asynchronously via Celery. Ensure the worker runs: `docker compose up -d celery-worker`.
- **Empty search results:** Upload documents first. Verify you use the correct tenant API key.
- **Tenant lost after restart:** Use `docker compose stop`/`start` instead of `docker compose down`.
- **UI shows wrong provider:** Check `CHAT_PROVIDER` in `.env`, restart the API, refresh browser.

More: [Developer guide](DEVELOPER_GUIDE.md), [Operations](OPERATIONS.md).
