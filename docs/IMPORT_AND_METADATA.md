# Importing Documents and Metadata for Better Search

How to import books/documents, what metadata is stored, and how it improves search and display. This doc covers the **scope** of metadata (book, edition, chapter, section) and how it flows into the vector store and API.

---

## How to import documents

### Upload API (recommended)

- **POST /upload/document** (multipart form):
  - **Required:** `file` (.txt or .pdf), `title`, `author`, `edition_name`
  - **Optional:** `publication_year`, `async_mode` (1 = return 202 + job, poll **GET /ingest/status/{job_id}**)

Example:

```bash
curl -X POST http://localhost:8080/upload/document \
  -H "X-API-Key: YOUR_KEY" \
  -F "file=@/path/to/book.pdf" \
  -F "title=My Book" \
  -F "author=Author Name" \
  -F "edition_name=2024" \
  -F "publication_year=2024"
```

### Programmatic ingestion

Use **IngestionPipeline** in code:

1. **ensure_book_and_edition(tenant_id, title, author, edition_name, publication_year=..., publisher=..., isbn=..., book_metadata=..., edition_metadata=...)**  
   Creates or reuses a Book and Edition. Optional `book_metadata` and `edition_metadata` are JSON objects stored in Postgres (and can be used later for filtering or display).

2. **ingest_from_blocks(book, edition, blocks)**  
   Or **ingest_raw_text(tenant_id, title, author, edition_name, raw_text, ...)**  
   Parses structure (chapters/sections), chunks, embeds, and writes to Postgres + Qdrant.

See [Developer guide](DEVELOPER_GUIDE.md) and `src/ingestion/ingestion_pipeline.py`.

---

## Where metadata is stored

| Layer | What is stored |
|-------|----------------|
| **PostgreSQL** | **Books:** title, author, isbn, created_at, optional **metadata** (JSONB). **Editions:** edition_name, publication_year, publisher, version_hash, ingested_at, optional **metadata** (JSONB). **Sections:** full text, chapter/section numbers and titles, location_path, canonical_section_id, etc. |
| **Qdrant (vectors)** | Each section and chunk vector has a **payload** used for filtering and for returning rich results. |

---

## Vector payload (Qdrant) – used for search and display

Every **section** and **chunk** point in Qdrant includes these payload fields so search results can be filtered and displayed without extra DB lookups:

| Field | Description | Use |
|-------|--------------|-----|
| section_id, edition_id, book_id, tenant_id | Identifiers | Filtering, joins |
| canonical_section_id, location_path | Stable section identity | Compare across editions |
| chapter_number, section_number | Structure | Filter / sort by position |
| content_preview (section) / chunk_text (chunk) | Text snippet | Snippets in UI |
| **book_title**, **book_author** | Document-level | Display “From: Title by Author”, filter by title/author (future) |
| **edition_name**, **publication_year** | Edition-level | Display edition, filter by year (future) |
| **chapter_title**, **section_title** | Chapter/section-level | Display “Chapter 3: Introduction”, filter by chapter (future) |

Search and compare responses already return **document_id**, **book_title**, **book_author**, **edition_name**, **chapter_title**, **section_title** when the vectors were ingested with this payload (all new ingestions include them).

---

## Scope: what you can add today

### Already supported

- **On upload:** title, author, edition_name, publication_year (and optionally publisher, isbn via pipeline).
- **In Postgres:** Book has **metadata** (JSONB); Edition has **metadata** (JSONB). Use these for custom key-value (e.g. `language`, `description`, `tags`, `source_url`). Set them when creating the book/edition in code (e.g. `book_metadata={"language": "en", "tags": ["fiction"]}`).
- **In vectors:** Book title/author, edition name/year, chapter title, section title are stored in every section and chunk payload and returned in search/citations.

### Optional: extend upload form

You can add more form fields to **POST /upload/document** (e.g. `publisher`, `isbn`, or a JSON string for `book_metadata` / `edition_metadata`) and pass them into `IngestionPipeline.ensure_book_and_edition` and then into the pipeline. The pipeline already accepts `book_metadata` and `edition_metadata`; the upload handler can be extended to parse and pass them.

### Optional: filter by metadata in search

Today, search filters by **document_id** and **edition_id**. You can extend **POST /search** (and the Qdrant client) to support filters such as:

- **book_title** (exact or keyword)
- **edition_name** or **publication_year**
- **chapter_title** (e.g. “only Chapter 5”)

Qdrant supports filter conditions on payload fields; you would add the corresponding query parameters and build `filter_conditions` in `search_sections` / `search_chunks`.

---

## Chapter-wise and “book details” summary

- **Book-level:** Stored in Postgres (title, author, isbn, metadata JSONB). Also copied into every vector payload as **book_title**, **book_author** for display and future filtering.
- **Edition-level:** Postgres (edition_name, publication_year, publisher, metadata JSONB). In payload: **edition_name**, **publication_year**.
- **Chapter/section-level:** Postgres has **chapter_number**, **chapter_title**, **section_number**, **section_title**, **subsection_***, **location_path**. All of these are available in the ingestion pipeline and are stored in the vector payload as **chapter_title**, **section_title** (and location_path). So “chapter-wise details” are already in the vector store; you can show them in search results and later add filters (e.g. by chapter title).

Adding more “book details” (e.g. description, language, tags) is done via **Book.metadata** or **Edition.metadata**; you can then surface them in **GET /documents** or in search by extending the API to include metadata in responses or to filter by it in Qdrant after adding those fields to the payload (if needed).

---

## Future scope (ideas)

- **Filter by metadata in API:** Add query params to **POST /search** for book_title, publication_year, chapter_title, etc., and map them to Qdrant filters.
- **Chapter index:** A dedicated endpoint or response shape that lists chapters (and optionally section counts) per document/edition, using existing section/chapter fields in Postgres.
- **Full-text + vector:** Keep using vector search as primary; optionally combine with Postgres full-text search on section content for hybrid ranking.
- **Bulk import:** Script or endpoint to ingest many files (e.g. from a folder or S3) with a CSV or JSON manifest for title/author/edition/metadata.
- **Re-ingest with new metadata:** If you add new metadata to Book/Edition (e.g. tags), you could run a job to update only the payload of existing vectors (same vector, new payload) so search results reflect the new metadata without re-embedding.

---

## See also

[API reference](api_reference.md) · [Architecture & design](ARCHITECTURE_AND_DESIGN.md) · [Features](FEATURES.md)
