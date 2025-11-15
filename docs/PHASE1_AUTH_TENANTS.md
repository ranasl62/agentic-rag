# Phase 1: Auth + Tenant Isolation — Detailed Specification

This document is the **single source of truth** for Phase 1 implementation. It refines the scope from `PRODUCTION_ROADMAP_60K.md` and defines the execution plan, agent assignments, data model, API contract, and tenant-scoping rules.

---

## 1. Scope and Goals

- **Goal:** Every request is tied to a **tenant** (dealer or brand). Data and search are scoped so tenants only access their own manuals.
- **Out of scope for Phase 1:** JWT/OIDC, rate limiting, caching, async ingestion, multi-key per tenant (one API key per tenant is enough).

---

## 2. Execution Plan (Ordered Tasks)

Tasks are ordered by dependency. Dependencies are implied by order (later tasks depend on earlier ones).

| # | Task | Owner (Agent) | Depends on |
|---|------|----------------|------------|
| 1 | Add `Tenant` model and `tenant_id` on `Book`; extend `init_db`; add migration/backfill script for existing DBs | **Data/DB** | — |
| 2 | Add `tenant_id` to Qdrant section/chunk payloads in ingestion; add `tenant_id` to all Qdrant search/scroll filters | **Data/DB** + **Ingestion** | 1 |
| 3 | Add auth settings (API key validation); implement `get_current_tenant()` dependency and optional `require_tenant` middleware | **Auth** | 1 |
| 4 | Scope **upload**: require auth, set `tenant_id` on created books and in ingestion/Qdrant | **API/Scope** | 2, 3 |
| 5 | Scope **list books** and **list sections**: filter by `tenant_id` (via Book) | **API/Scope** | 3 |
| 6 | Scope **search** (POST /search): add `tenant_id` to Qdrant filter_conditions | **API/Scope** | 2, 3 |
| 7 | Scope **compare** (POST /compare): restrict to sections belonging to tenant’s books | **API/Scope** | 3 |
| 8 | Scope **summarize** (POST /summarize): restrict to sections belonging to tenant’s books | **API/Scope** | 3 |
| 9 | Scope **query** (POST /query): pass `tenant_id` into orchestrator and all tools (search, find_same, list_editions, match, compare, summarize) | **API/Scope** | 2, 3 |
| 10 | Update **tools** to accept and use `tenant_id` in every DB and Qdrant call | **API/Scope** | 2, 3 |
| 11 | Document: how to create tenants, issue API keys, and call the API | **Docs** | 1–10 |

---

## 3. Agent / Role Assignment

Work can be split across these roles:

- **Data/DB agent:** Schema changes, migrations, backfill, Qdrant payload and filter changes in the storage layer.
- **Auth agent:** API key storage/validation, `get_current_tenant` dependency, 401/403 behavior.
- **API/Scope agent:** All route and tool changes that enforce tenant_id (upload, books, sections, search, compare, summarize, query, tools).
- **Docs agent:** Phase 1 user/admin documentation.

Parallelization: **Data/DB** and **Auth** can start after task 1; **API/Scope** needs tasks 2 and 3 done before scoping routes and tools.

---

## 4. Data Model

### 4.1 New table: `tenants`

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `tenant_id` | UUID (PK) | No | Unique tenant identifier |
| `name` | TEXT | No | Display name (e.g. "Acme Dealers") |
| `slug` | TEXT | No | Unique slug (e.g. "acme-dealers") |
| `api_key_hash` | TEXT | Yes | SHA-256 hash of the API key (lowercase, no prefix) |
| `created_at` | TIMESTAMP | No | Creation time |
| `metadata` | JSONB | Yes | Optional extra data |

- **Unique constraint:** `slug`.
- **Lookup for auth:** by `api_key_hash` (client sends raw API key in header; server hashes and finds tenant).

### 4.2 Changes to existing tables

- **`books`**
  - Add `tenant_id` UUID NOT NULL REFERENCES `tenants(tenant_id)`.
  - Add index on `tenant_id` for list/filter performance.
  - **Backfill:** Create one default tenant (e.g. slug `default`, name "Default Tenant"), then `UPDATE books SET tenant_id = <default_tenant_id> WHERE tenant_id IS NULL` (if we add column as nullable first, then set default, then alter to NOT NULL).

- **Editions:** No direct `tenant_id`; tenant is derived via `Edition` → `Book` → `tenant_id`.

- **Sections / SectionChunk / SectionAlignment:** No schema change; tenant is derived via Section → Edition → Book → tenant_id.

### 4.3 Qdrant payloads

- **Section collection** (`section_embeddings`): Add `tenant_id` (string UUID) to every payload in `upsert_section_vector`. Used in `search_sections` and `scroll_sections_by_canonical` filters.
- **Chunk collection** (`chunk_embeddings`): Add `tenant_id` to every payload in `upsert_chunk_vectors`. Used in `search_chunks` filter when/if used.

**Migration for existing points:** Existing vectors have no `tenant_id`. Options: (a) Backfill Qdrant by re-upserting with tenant_id (requires re-running ingestion or a one-off script that reads from Postgres and updates payloads); (b) For Phase 1, treat missing `tenant_id` in payload as “legacy” and filter with `must: [tenant_id OR tenant_id is null]` only if we keep a default tenant for legacy data. **Recommended:** Backfill script that scrolls sections/chunks, gets section_id → edition → book → tenant_id from Postgres, then updates payload with tenant_id. Alternatively, require re-ingestion for existing data and enforce tenant_id present for all new data.

---

## 5. Auth Mechanism (Phase 1: API Key Only)

- **Method:** API key per tenant.
- **Header:** `X-API-Key: <secret>` (or `Authorization: Bearer <secret>`; we use `X-API-Key` for clarity).
- **Validation:**
  1. Read key from `X-API-Key` header.
  2. If missing or empty → **401 Unauthorized** (for protected routes).
  3. Compute hash: `SHA-256(key.strip().lower().encode()).hexdigest()` (normalize so key is case-insensitive for lookup).
  4. Look up tenant by `api_key_hash` in `tenants` table.
  5. If not found → **401 Unauthorized**.
  6. Set `request.state.tenant_id` (UUID) and optionally `request.state.tenant_slug`.

- **Dependency:** `get_current_tenant(request) -> TenantInfo` (or just `tenant_id: UUID`). Use as dependency on all routes that touch tenant-scoped data. For health/debug we can leave some routes unauthenticated (see API contract below).

- **Storage of keys:** We do **not** store raw API keys. Store only `api_key_hash`. Admin creates tenant and generates a one-time secret; they must store it (e.g. in env) and pass it in `X-API-Key`.

- **Config:** Optional env `REQUIRE_AUTH=true` to require auth on all data endpoints; if `false`, support a "default" tenant when header is missing (for local dev). Default: `REQUIRE_AUTH=true` in production.

---

## 6. API Contract

### 6.1 Endpoints that require auth (tenant context)

All of these **must** use `get_current_tenant` and scope by `tenant_id`:

- `POST /upload/document` — require auth; set book.tenant_id from request.
- `GET /books` — require auth; filter books by tenant_id.
- `GET /books/sections` — require auth; filter sections by tenant (via edition → book).
- `POST /search` — require auth; add tenant_id to Qdrant filter.
- `POST /compare` — require auth; restrict sections to tenant’s books.
- `POST /summarize` — require auth; restrict sections to tenant’s books.
- `POST /query` — require auth; pass tenant_id to orchestrator/tools.

### 6.2 Endpoints that may remain public (no tenant)

- `GET /health` — no auth.
- Optional: `GET /debug/...` — can remain public for ops (or guard by env); no tenant.

### 6.3 Error responses

- **401 Unauthorized:** Missing or invalid API key. Body: `{"detail": "Invalid or missing API key"}` (or similar).
- **403 Forbidden:** Reserved for future use (e.g. valid token but tenant disabled).

### 6.4 Passing tenant_id

- **Never** accept `tenant_id` from request body or query for authorization. Tenant is **only** derived from the API key. This prevents privilege escalation.

---

## 7. Tenant-Scoping Rules (Exact)

| Area | Rule |
|------|------|
| **Upload** | On create: `Book.tenant_id = request.state.tenant_id`. Ingestion pipeline receives `tenant_id`, passes it to `ensure_book_and_edition` (set on book) and to every Qdrant upsert payload. |
| **List books** | `SELECT * FROM books WHERE tenant_id = :tenant_id ORDER BY title`. |
| **List sections** | Same as now, but join through Edition → Book and add `WHERE Book.tenant_id = :tenant_id`. |
| **Search (POST /search)** | Build `filter_conditions` with `tenant_id = request.state.tenant_id` in addition to any book_id/edition_id. Qdrant `search_sections` must include tenant_id in filter. |
| **Compare (POST /compare)** | When loading sections by canonical_section_id or by book_id+chapter+section: only allow sections whose edition’s book has `book.tenant_id = request.state.tenant_id`. Qdrant `scroll_sections_by_canonical` must filter by `tenant_id`. |
| **Summarize (POST /summarize)** | When loading sections by section_ids or by query: only allow sections that belong to tenant (section → edition → book → tenant_id). For query path, orchestrator/tools already receive tenant_id and filter. |
| **Query (POST /query)** | Orchestrator and every tool receive `tenant_id` (from request). Search tool: add tenant_id to Qdrant filter. Find_same_section: filter Qdrant and DB by tenant_id. List_available_editions: filter by tenant_id. Match_sections: only consider sections within tenant. Compare/summarize tools: already receive section IDs that were resolved with tenant scope. |
| **Tools** | `SearchSectionsTool`: add `tenant_id` to `filter_conditions` in `search_sections`. `FindSameSectionAcrossEditionsTool`: when using Qdrant `scroll_sections_by_canonical`, add `tenant_id` to filter; when using DB, join Book and filter by `Book.tenant_id`. `ListAvailableEditionsTool`: join Book, filter by `Book.tenant_id`. `MatchSectionsTool`: ensure source/target sections belong to tenant (e.g. join Book and filter by tenant_id). |

---

## 8. Migration and Backfill

### 8.1 New deployments

- `init_db()` creates `tenants` and adds `tenant_id` to `books` (with FK). Create one default tenant and set it as default for any bootstrap data if needed.

### 8.2 Existing deployments (already have `books` without `tenant_id`)

1. Create `tenants` table and add column `books.tenant_id` as NULLable.
2. Insert one default tenant (e.g. slug `default`).
3. `UPDATE books SET tenant_id = (SELECT tenant_id FROM tenants WHERE slug = 'default' LIMIT 1)`.
4. Alter `books.tenant_id` to NOT NULL and add FK.
5. (Optional) Qdrant backfill: script that for each section/chunk point in Qdrant, looks up tenant_id from Postgres (section → edition → book → tenant_id) and updates payload. Alternatively, document that existing vectors are “legacy” and will be replaced on next re-ingestion (and new ingestions always write tenant_id).

A small Python script `scripts/backfill_tenant.py` can do steps 2–4 using asyncpg or SQLAlchemy sync. Qdrant backfill can be a separate script.

---

## 9. Configuration (env)

- `REQUIRE_AUTH` (default `true`): If `true`, protected endpoints return 401 when API key is missing. If `false`, use a default tenant when key is missing (for local dev).
- `DEFAULT_TENANT_ID` or `DEFAULT_TENANT_SLUG` (optional): When `REQUIRE_AUTH=false`, which tenant to use when header is missing.

---

## 10. Files to Touch (Checklist)

- **Models / DB:** `src/storage/models.py` (Tenant, Book.tenant_id); `src/storage/postgres_client.py` (init_db; optional backfill helper).
- **Migrations:** New script `scripts/backfill_tenant.py` (or under `migrations/`) for existing DBs.
- **Config:** `config/settings.py` (REQUIRE_AUTH, DEFAULT_TENANT_SLUG).
- **Auth:** New `src/api/auth.py` (hash function, get_current_tenant dependency, 401 handling).
- **Qdrant:** `src/storage/qdrant_client.py` (add tenant_id to search/scroll filters); ingestion: `src/ingestion/ingestion_pipeline.py` (accept tenant_id, set on book, add to payloads).
- **Routes:** `src/api/routes/upload.py`, `books.py`, `search.py`, `compare.py`, `summarize.py`; `src/api/main.py` (query endpoint) — add Depends(get_current_tenant) and pass tenant_id where needed.
- **Tools:** `src/tools/search_tools.py` (SearchSectionsTool, FindSameSectionAcrossEditionsTool, ListAvailableEditionsTool); `src/tools/matching_tools.py` (MatchSectionsTool); `src/api/dependencies.py` (inject tenant_id into tools or pass via orchestrator).
- **Orchestrator:** `src/agents/orchestrator.py` — accept tenant_id and pass to tools.
- **Docs:** `docs/PHASE1_AUTH_TENANTS.md` (this file); add a short “Using the API” section for creating tenants and calling with X-API-Key.

---

## 11. Validating Phase 1 and Using the Chatbot

### Validation

- **Against a running API (recommended):**  
  Start the API (e.g. `uv run uvicorn src.api.main:app --reload`), then:
  ```bash
  # With default tenant (set REQUIRE_AUTH=false in .env):
  uv run python -m scripts.validate_phase1_live

  # With API key:
  AGENT_API_KEY=your-key uv run python -m scripts.validate_phase1_live
  ```
  The script checks: `/health`, `/books`, `/books/sections`, `/search`, `/compare`, `/summarize`, `/query` (status and response shape).

- **Unit/integration tests (require Postgres + Qdrant):**  
  ```bash
  uv sync --extra dev
  uv run python -m pytest tests/test_phase1_validation.py -v
  ```
  Without a running Postgres, tests that use the TestClient will fail at startup (lifespan); use the live script above instead.

### Interactive chatbot

One interactive chatbot talks to the agentic RAG via `POST /query` (tenant-scoped):

```bash
# Default tenant (REQUIRE_AUTH=false):
uv run python -m scripts.chat

# With API key:
AGENT_API_KEY=your-key uv run python -m scripts.chat

# Custom API URL:
API_BASE_URL=http://localhost:8080 uv run python -m scripts.chat
```

In the chat: type your question and press Enter; the agent will search, compare, or summarize as needed. Commands: `/quit` or `/exit` to exit, `/help` for help.

---

## 12. Using the API (Phase 1)

- **Create a tenant and API key:** Run `uv run python -m scripts.create_tenant "Tenant Name" slug` (e.g. `scripts.create_tenant "Acme Dealers" acme-dealers`). The script creates the tenant and prints an API key once; store it securely. Alternatively, insert a row into `tenants` with `name`, `slug`, and `api_key_hash = SHA256(your_secret_key.strip().lower()).hexdigest()`.
- **Call protected endpoints:** Send header `X-API-Key: <your_secret_key>` on every request to `/upload/document`, `/books`, `/books/sections`, `/search`, `/compare`, `/summarize`, `/query`.
- **Local dev without keys:** Set `REQUIRE_AUTH=false` and `DEFAULT_TENANT_SLUG=default`. The app creates a default tenant at startup; requests without `X-API-Key` use that tenant.
- **Existing DBs:** Run `python -m scripts.backfill_tenant` once to add `tenants` and `books.tenant_id` and assign existing books to the default tenant.

---

## 13. Summary

Phase 1 adds a **tenants** table and **tenant_id** on books and in Qdrant payloads, **API key auth** with a **get_current_tenant** dependency, and **tenant-scoping** on upload, list books/sections, search, compare, summarize, and query (including all tools). No tenant_id is taken from the client; it is always derived from the API key. After implementation, all data and vector operations are isolated per tenant.
