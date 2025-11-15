# Documentation

> Full documentation for the **Agentic RAG** system. Ingest any document (PDF, TXT), search, compare editions, and summarize with tool-based agents.

---

## Navigation

| Section | Documents |
|--------|-----------|
| **Getting started** | [Overview & scope](OVERVIEW_AND_SCOPE.md) · [User guide](USER_GUIDE.md) |
| **Design & development** | [Architecture & design](ARCHITECTURE_AND_DESIGN.md) · [Developer guide](DEVELOPER_GUIDE.md) · [Architecture](architecture.md) |
| **Testing** | [Testing guide](TESTING_GUIDE.md) · [Phase 1–6 validation](VALIDATION_PHASE1_PHASE2_PHASE3.md) |
| **API & operations** | [API reference](api_reference.md) · [Production roadmap](PRODUCTION_ROADMAP_60K.md) · [Phase alignment](PHASE1_PHASE6_ALIGNMENT.md) · [Runbooks](runbooks/) |

---

## Getting started

| Document | Description |
|----------|-------------|
| [**Overview & scope**](OVERVIEW_AND_SCOPE.md) | What problem we solve, supported documents (any type), capabilities, audience. |
| [**User guide**](USER_GUIDE.md) | Upload, search, compare two editions. For end users. |

---

## Design & development

| Document | Description |
|----------|-------------|
| [**Architecture & design**](ARCHITECTURE_AND_DESIGN.md) | System design: API, orchestrator, agents, tools, storage, data flow, production stack. |
| [**Developer guide**](DEVELOPER_GUIDE.md) | Code layout, local setup, config, extending (tools, agents, endpoints). |
| [**Architecture**](architecture.md) | High-level diagram and design decisions. |

---

## Testing

| Document | Description |
|----------|-------------|
| [**Testing guide**](TESTING_GUIDE.md) | Test the **whole** app: unit tests (Phase 1–6), live validation, E2E flow, quick reference. |
| [**Phase 1–6 validation**](VALIDATION_PHASE1_PHASE2_PHASE3.md) | Phase-by-phase check and test guide, prerequisites, expected results. |

---

## API & operations

| Document | Description |
|----------|-------------|
| [**API reference**](api_reference.md) | Base URL, auth, curl examples. |
| [**Production roadmap**](PRODUCTION_ROADMAP_60K.md) | Phases 1–6: auth, rate limit, cache, async ingest, scaling, monitoring. |
| [**Phase 1–6 alignment**](PHASE1_PHASE6_ALIGNMENT.md) | Map of phases to docs, scripts, tests. |
| [**Runbooks**](runbooks/) | add-capacity, backup-restore, failover, monitoring. |

---

## Phase & feature docs

| Phase | Document |
|-------|----------|
| 1 | [Auth & tenants](PHASE1_AUTH_TENANTS.md) |
| 2 | [Rate limit & cache](PHASE2_RATE_LIMIT_CACHE.md) |
| 3 | [Async ingestion](PHASE3_ASYNC_INGESTION.md) |
| 4 | [API scaling](PHASE4_API_SCALING.md) |
| 5 | [Qdrant & Postgres scaling](PHASE5_QDRANT_POSTGRES_SCALING.md) |
| 6 | [Monitoring & alerts](PHASE6_MONITORING_ALERTS.md) |

Other: [Agent prompts](agent_prompts.md) · [Models & observability](MODELS_AND_OBSERVABILITY.md) · [Document scope & vehicle metadata](DOCUMENT_SCOPE_AND_VEHICLE_METADATA.md)
