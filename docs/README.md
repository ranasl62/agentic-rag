# Documentation

**Agentic RAG**: ingest documents (PDF/TXT), search by meaning, compare editions, summarize with citations. Open source and self-hosted.

---

## Key URLs

| Purpose | Docker (Nginx) | Local API |
|---------|---------------|-----------|
| Health | http://localhost:8080/health | http://localhost:8000/health |
| Swagger UI | http://localhost:8080/docs | http://localhost:8000/docs |
| API info | http://localhost:8080/info | http://localhost:8000/info |
| Metrics | http://localhost:8080/metrics | http://localhost:8000/metrics |
| Web UI | http://localhost:3002 | http://localhost:3000 |

**Port:** With Docker + Nginx the API is on **8080** (configurable via `API_PORT` in `.env`). Without Docker use **8000**.
`/metrics` returns 404 when `METRICS_ENABLED=false`; set `METRICS_ENABLED=true` and restart to enable.

---

## Docs

| Doc | Description |
|-----|-------------|
| [Getting started](GETTING_STARTED.md) | Run with Docker or local API; env, providers, tenant setup. |
| [User guide](USER_GUIDE.md) | Upload, search, compare editions via API and web UI. |
| [Overview & scope](OVERVIEW_AND_SCOPE.md) | What it does, what documents it supports. |
| [API reference](api_reference.md) | Endpoints, auth, request/response examples. |
| [Features](FEATURES.md) | Ingestion, search, compare, agents, auth, async upload. |
| [Tech stack](TECH_STACK.md) | Python, FastAPI, Postgres, Qdrant, Redis, Nginx. |
| [Models & observability](MODELS_AND_OBSERVABILITY.md) | OpenAI, Anthropic, Ollama; metrics and logging. |
| [Import & metadata](IMPORT_AND_METADATA.md) | Import docs, metadata in vectors. |
| [Architecture & design](ARCHITECTURE_AND_DESIGN.md) | API, orchestrator, tools, data flow. |
| [System design diagrams](SYSTEM_DESIGN_DIAGRAM.md) | Mermaid diagrams: architecture, pipelines, data model. |
| [Developer guide](DEVELOPER_GUIDE.md) | Code layout, extend tools/agents. |
| [Testing guide](TESTING_GUIDE.md) | Unit tests, live validation. |
| [Deployment](DEPLOYMENT.md) | Production: auth, rate limits, scaling. |
| [Operations](OPERATIONS.md) | Runbooks, backup, monitoring. |

---

## Screenshots

| Image | Doc |
|-------|-----|
| [frontend.png](screenshot/frontend.png) | [User guide](USER_GUIDE.md) |
| [swagger.png](screenshot/swagger.png) | [API reference](api_reference.md) |
| [qdrant.png](screenshot/drant.png) | [Tech stack](TECH_STACK.md) |
