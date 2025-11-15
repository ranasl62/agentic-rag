# API Reference

Base URL: `http://localhost:8080` when using Docker (Nginx); `http://localhost:8080` when running the API alone (or your deployed host).

## Health

- **GET /health** — Returns `{"status": "ok"}`.

## Upload (create editions)

- **POST /upload/document** (multipart form)  
  Upload a document as one edition of a book. Same title + author with different `edition_name` = multiple versions to compare.  
  - **file** (required): `.txt` or `.pdf`  
  - **title** (required): Book title  
  - **author** (required): Author  
  - **edition_name** (required): e.g. `2015`, `2021`, `First Edition`  
  - **publication_year** (optional): integer  
  Returns: `{ "success", "message", "title", "author", "edition_name", "sections_count" }`.

## Search

- **POST /search**  
  Body: `{ "query": "string", "limit": 10, "book_id": "uuid?", "edition_id": "uuid?" }`  
  Returns semantic search results with section metadata and citations.

## Compare

- **POST /compare**  
  Body: `{ "book_id": "uuid", "canonical_section_id": "string?", "chapter_number": int?, "section_number": int?, "edition_ids": ["uuid"]? }`  
  Returns the same section across editions (by canonical id or chapter/section numbers).

## Summarize

- **POST /summarize**  
  Body: `{ "section_ids": ["uuid"]?, "query": "string?", "max_length": 300 }`  
  - If `section_ids` has one id: summarize that section.  
  - If two or more: summarize differences across those sections.  
  - If `query` only: run orchestrator and return summary from agent pipeline.

## Books and Sections

- **GET /books** — List all books and their editions.  
- **GET /books/sections?book_id=uuid&edition_id=uuid** — List sections (optionally filtered by book or edition).

## Agentic Query

- **POST /query**  
  Body: `{ "query": "Compare Chapter 5 Section 2 between 2015 and 2021 editions", "skip_verification": false }`  
  Runs the full pipeline: query understanding → retrieval plan → tools → compare/summarize → verification.  
  Returns: `{ "response": "...", "steps": [...], "citations": [...], "verified": bool }`.

## Example Calls

```bash
# Search
curl -X POST http://localhost:8080/search -H "Content-Type: application/json" -d '{"query": "introduction to algorithms", "limit": 5}'

# List books
curl http://localhost:8080/books

# Compare (after ingesting two editions)
curl -X POST http://localhost:8080/compare -H "Content-Type: application/json" -d '{"book_id": "<book-uuid>", "chapter_number": 5, "section_number": 2, "edition_ids": ["<ed1>", "<ed2>"]}'

# Agent query
curl -X POST http://localhost:8080/query -H "Content-Type: application/json" -d '{"query": "Summarize how this topic evolved across editions"}'
```
