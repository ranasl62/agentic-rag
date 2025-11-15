# Agentic RAG System Architecture

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     API Layer (FastAPI)                          │
│  /search  /compare  /summarize  /books  /sections  /query         │
└────────────────────────────┬────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────┐
│                      Agent Orchestrator                          │
│  Query Understanding → Retrieval Planning → Tool Execution       │
│  → Comparison/Summarization → Verification                      │
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
│  sections  summarize_section  summarize_differences  list_       │
│  available_editions  match_sections                              │
└────────────────────────────┬────────────────────────────────────┘
                             │
         ┌───────────────────┼───────────────────┐
         ▼                   ▼                   ▼
   Qdrant (vectors)    Ollama (LLM+emb)    PostgreSQL (metadata)
   Redis (cache)
```

## Design Decisions

1. **Local-first**: All services (Ollama, Qdrant, Postgres, Redis) run locally or in your Docker network; no external SaaS required.
2. **Tool-based agents**: Agents do not call each other directly; they produce structured output (intent, plan) and the orchestrator invokes tools. This keeps steps deterministic and testable.
3. **Stable section IDs**: `canonical_section_id` (e.g. `book_xxx_ch03_sec02`) is derived from structure (chapter/section numbers) so the same logical section across editions can be matched without relying only on semantic similarity.
4. **Dual storage**: PostgreSQL holds metadata and full section text; Qdrant holds embeddings only. Filtering and listing use Postgres; semantic search uses Qdrant with payload filters.
5. **Semantic chunking**: Sections are chunked by paragraph/sentence boundaries with size limits, not fixed character windows, to keep meaning intact.
6. **Verification agent**: Optional step to check that the final answer is grounded in retrieved context and to flag unsupported claims.
7. **Async throughout**: API and tools are async for scalability; ingestion and search can run concurrently.

## Data Flow

- **Ingestion**: Raw text → structure extraction (chapters/sections) → canonical ID + location_path → semantic chunking → embed (Ollama) → store (Postgres + Qdrant).
- **Query**: User query → Query Understanding (intent, entities) → Retrieval Planning (which tools, which params) → run tools → assemble sections → Comparison or Summarization agent → optional Verification → response with citations.

## Multi-Tenant Readiness

- Metadata includes `book_id` and `edition_id`; Qdrant filters support `book_id`/`edition_id`. Adding a `tenant_id` to tables and payloads would allow per-tenant isolation without changing the agent/tool logic.
