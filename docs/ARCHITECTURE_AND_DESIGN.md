# Architecture & Design

How the Agentic RAG system is built: components, data flow, and design decisions. For a short overview and scope (what problem we solve, what documents we support), see [Overview & scope](OVERVIEW_AND_SCOPE.md).

---

## High-level architecture

The system has four main layers: **API**, **orchestrator + agents**, **tools**, and **storage**. Documents flow in via ingestion; queries flow in via the API and are executed by the orchestrator using agents and tools.

```
┌─────────────────────────────────────────────────────────────────┐
│                     API Layer (FastAPI)                          │
│  /search  /compare  /summarize  /books  /sections  /query        │
│  /upload/document  /ingest/status  /health  /metrics            │
└────────────────────────────┬────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────┐
│                      Agent Orchestrator                          │
│  Query Understanding → Retrieval Planning → Tool Execution      │
│  → Comparison/Summarization → Verification                       │
└────────────────────────────┬────────────────────────────────────┘
                             │
         ┌───────────────────┼───────────────────┐
         ▼                   ▼                   ▼
   Query Agent      Retrieval Agent      Section Matching Agent
   Comparison Agent Summarization Agent  Verification Agent
                             │
┌────────────────────────────▼────────────────────────────────────┐
│                         Tool Layer                               │
│  search_sections  find_same_section_across_editions  compare_     │
│  sections  summarize_section  summarize_differences  list_      │
│  available_editions  match_sections                              │
└────────────────────────────┬────────────────────────────────────┘
                             │
         ┌───────────────────┼───────────────────┐
         ▼                   ▼                   ▼
   Qdrant (vectors)    Ollama (LLM+emb)    PostgreSQL (metadata)
   Redis (cache, rate limit, Celery broker)
```

---

## Design decisions

| Decision | Rationale |
|----------|-----------|
| **Local-first** | Ollama (or OpenAI) for LLM/embeddings; Qdrant; Postgres; Redis. No required SaaS; you control data and models. |
| **Tool-based agents** | Agents do not call each other directly. They produce structured output (intent, plan); the **orchestrator** invokes **tools**. This keeps steps deterministic, testable, and auditable. |
| **Stable section identity** | `canonical_section_id` (e.g. `book_xxx_ch03_sec02`) is derived from document structure (chapter/section numbers). The same logical section across editions can be matched by this ID instead of only semantic similarity. |
| **Dual storage** | **PostgreSQL**: metadata (books, editions, sections, full text). **Qdrant**: embeddings and payloads for vector search. Filtering and listing use Postgres; semantic search uses Qdrant with payload filters (tenant_id, book_id, edition_id). |
| **Semantic chunking** | Sections are chunked by paragraph/sentence boundaries with size limits, not fixed character windows, to keep meaning intact for retrieval. |
| **Verification agent** | Optional final step to check that the answer is grounded in retrieved context and to flag unsupported claims. |
| **Multi-tenant from the start** | Every request is scoped to a **tenant** (via API key). All DB and Qdrant reads/writes filter by `tenant_id`. |

---

## Data flow

### Ingestion

1. **Input**: PDF or TXT file; metadata: title, author, edition name (and optional publication year, tenant).
2. **Parse**: PDF → text extraction; then same path as TXT.
3. **Structure**: The structure extractor detects chapters and sections from headings. Produces a tree: book → edition → chapter → section → (optional) subsection.
4. **Canonical IDs**: Each section gets a stable `canonical_section_id` from its position (e.g. ch03, sec02) so the same section in another edition can be matched.
5. **Chunking**: Each section is split into **semantic chunks** (paragraph/sentence boundaries, max size). Each chunk keeps a reference to section and edition.
6. **Embedding**: Chunk text is embedded (Ollama or OpenAI) and stored in **Qdrant** with payload: tenant_id, book_id, edition_id, section_id, canonical_section_id, etc.
7. **Metadata**: Books, editions, sections (and full section text) are stored in **PostgreSQL**. Qdrant holds only vectors + payloads.

Ingestion can run **synchronously** (upload and wait for 200) or **asynchronously** (upload returns 202 + job_id; Celery worker processes in background; client polls `GET /ingest/status/{job_id}`).

### Query

1. **Request**: User sends a natural-language query (e.g. “Compare Chapter 5 Section 2 between 2015 and 2021 editions”) to `POST /query`, or uses direct endpoints (`/search`, `/compare`, `/summarize`).
2. **Auth & rate limit**: Request is tied to a tenant (API key); rate limits and optional cache are applied.
3. **Query understanding**: The **Query Understanding** agent parses the query into intent (e.g. compare, summarize, search) and entities (book, chapter, section, edition IDs or names).
4. **Retrieval planning**: The **Retrieval Planning** agent decides which **tools** to call and with what parameters (e.g. `find_same_section_across_editions`, then `compare_sections`).
5. **Tool execution**: The orchestrator runs the chosen tools. Tools use **Qdrant** for vector search (with tenant_id and optional filters) and **Postgres** for metadata and full text.
6. **Comparison / summarization**: The **Comparison** or **Summarization** agent takes retrieved sections and produces an answer (and optional diff/summary). LLM calls go to Ollama (or configured provider).
7. **Verification** (optional): The **Verification** agent checks that the answer is grounded in the retrieved context.
8. **Response**: The API returns the answer plus steps, citations, and verification flag. Results can be cached in Redis (per tenant + query) for repeat requests.

---

## Components in code

| Layer | Location | Purpose |
|-------|----------|---------|
| **API** | `src/api/main.py`, `src/api/routes/*` | FastAPI app, routes (search, compare, summarize, books, upload, ingest), auth, rate limit, cache, metrics. |
| **Orchestrator** | `src/agents/orchestrator.py` | Runs query understanding → retrieval planning → tool execution → comparison/summarization → verification. |
| **Agents** | `src/agents/` | query_understanding, retrieval_planning, section_matching, comparison, summarization, verification. Each uses LLM and structured output. |
| **Tools** | `src/tools/` | search_tools, matching_tools, comparison_tools, summarization_tools. Called by orchestrator; use storage and LLM. |
| **Storage** | `src/storage/` | postgres_client (metadata, books, sections), qdrant_client (vectors), redis_client (cache, rate limit). |
| **Ingestion** | `src/ingestion/` | ingestion_pipeline, structure_extractor, semantic_chunker, section_id_generator. |
| **LLM** | `src/llm/` | embeddings, chat_client (Ollama/OpenAI/Anthropic), prompt_templates. |
| **Worker** | `src/worker/` | Celery app and async ingest task (Phase 3). |

---

## Production stack (Phases 1–6)

Beyond the core RAG pipeline, the system supports production hardening:

| Phase | What | Where |
|-------|------|--------|
| **1** | Auth + tenant isolation | API key per tenant; `tenant_id` in DB and Qdrant; `get_current_tenant()`. |
| **2** | Rate limiting + Redis cache | Per-tenant (and optional per-IP) limits; search/query result cache with TTL. |
| **3** | Async ingestion | Celery + Redis; upload can return 202 + job_id; `GET /ingest/status/{job_id}`. |
| **4** | API scaling | Nginx load balancer in front of multiple API replicas; API on port 8080. |
| **5** | Qdrant + Postgres scaling | PgBouncer for Postgres; sizing and backup/restore. |
| **6** | Monitoring | Prometheus `GET /metrics`; structured request logging (request_id, tenant_id, duration). |

Details: [Deployment](DEPLOYMENT.md) and [Operations](OPERATIONS.md).

---

## What this enables

- **Any document**: Feed PDF or TXT (books, manuals, reports, articles). Structure is inferred; same pipeline for all.
- **Multi-edition**: Same “book” with different edition names → compare the same section across editions.
- **Multi-tenant**: Each tenant’s data and search are isolated; suitable for many customers or brands.
- **Testable**: Agents produce structured output; tools have clear inputs/outputs; unit and live tests cover each phase.

For extension points (new tools, new agents, document scope filters), see [Developer guide](DEVELOPER_GUIDE.md).
