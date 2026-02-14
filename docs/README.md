# Documentation

Documentation for **Agentic RAG**: ingest documents (PDF/TXT), search by meaning, compare editions, and summarize with citations. Open source and self-hosted.

---

## How to run and what's inside

| Document | Description |
|----------|-------------|
| [**Getting started**](GETTING_STARTED.md) | How to run: Docker and local API, env, Ollama, tenant setup, troubleshooting. |
| [**Tech stack**](TECH_STACK.md) | Tools: Python, FastAPI, Postgres, Qdrant, Redis, Ollama, Celery, Nginx. |
| [**Models and observability**](MODELS_AND_OBSERVABILITY.md) | Ollama, OpenAI, Anthropic; per-task models; optional LangSmith. |
| [**API reference**](api_reference.md) | Every endpoint, auth, request/response, examples. |
| [**Features**](FEATURES.md) | All features: ingestion, search, compare, agents, auth, scaling. |

---

## For everyone

| Document | Description |
|----------|-------------|
| [**Overview & scope**](OVERVIEW_AND_SCOPE.md) | What the system does, what documents it supports (any PDF/TXT), and who it’s for. |
| [**User guide**](USER_GUIDE.md) | Upload documents, search, and compare two editions step by step. |

---

## For developers

| Document | Description |
|----------|-------------|
| [**Architecture & design**](ARCHITECTURE_AND_DESIGN.md) | How the system is built: API, orchestrator, agents, tools, storage, and data flow. |
| [**Developer guide**](DEVELOPER_GUIDE.md) | Code layout, local setup, config, and how to extend (tools, agents, endpoints). |
| [**Testing guide**](TESTING_GUIDE.md) | Unit tests, live validation scripts, E2E flow, and quick reference. |
| [**API reference**](api_reference.md) | Base URL, auth, and curl examples for main endpoints. |

---

## For operators

| Document | Description |
|----------|-------------|
| [**Deployment**](DEPLOYMENT.md) | Production deployment: auth, rate limits, cache, async ingest, scaling, monitoring. |
| [**Operations**](OPERATIONS.md) | Runbooks: scaling, backup/restore, failover, and monitoring (Prometheus, alerts, logging). |

---

## Reference

| Document | Description |
|----------|-------------|
| [**Architecture**](architecture.md) | High-level diagram and design decisions. |
| [**Agent prompts**](agent_prompts.md) | Prompts used by query, retrieval, comparison, and summarization agents. |
| [**Models & observability**](MODELS_AND_OBSERVABILITY.md) | Ollama/OpenAI/Anthropic options and optional LangSmith. |
