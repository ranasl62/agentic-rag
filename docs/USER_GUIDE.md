# User Guide: Upload Documents and Compare Two Versions

This guide explains how to **upload documents**, **search** across them, and **compare two different editions/versions** of the same book. Examples use **http://localhost:8080** (Docker + Nginx). If you run the API alone, use port **8000** instead.

**Supported documents:** You can feed **any kind of document** the system supports: **PDF** and **plain text (TXT)**. Content can be books, manuals, reports, articles, specifications, or any structured text. The system is not limited to a single domain (e.g. it works for repair manuals, legal docs, technical guides, or general books). For more on scope and capabilities, see [Overview & scope](OVERVIEW_AND_SCOPE.md).

---

## 1. Upload documents (create editions)

Each uploaded file becomes **one edition** of a book. To compare two versions, upload the same book twice with different **edition names** (e.g. "2015" and "2021").

### Option A: API (curl)

**Upload a PDF or TXT file:**

```bash
curl -X POST "http://localhost:8080/upload/document" \
  -F "file=@/path/to/book_2015.pdf" \
  -F "title=Introduction to Algorithms" \
  -F "author=Cormen et al." \
  -F "edition_name=2015" \
  -F "publication_year=2015"
```

**Upload the second version (same title + author, different edition):**

```bash
curl -X POST "http://localhost:8080/upload/document" \
  -F "file=@/path/to/book_2021.pdf" \
  -F "title=Introduction to Algorithms" \
  -F "author=Cormen et al." \
  -F "edition_name=2021" \
  -F "publication_year=2021"
```

- **title** + **author**: Identify the book. Same title + author = same book, multiple editions.
- **edition_name**: Version label (e.g. `2015`, `2021`, `First Edition`). Required.
- **file**: `.txt` or `.pdf`. For PDF, text is extracted and then ingested.
- **publication_year**: Optional.

Response example:

```json
{
  "success": true,
  "message": "Ingested 42 sections.",
  "title": "Introduction to Algorithms",
  "author": "Cormen et al.",
  "edition_name": "2021",
  "sections_count": 42
}
```

### Option B: Swagger UI (browser)

1. Open **http://localhost:8080/docs**
2. Find **POST /upload/document**
3. Click **Try it out**
4. Fill in:
   - **file**: Choose your PDF or TXT
   - **title**: Book title
   - **author**: Author
   - **edition_name**: e.g. `2015` or `2021`
   - **publication_year**: (optional)
5. Click **Execute**

---

## 2. List books and editions (see what you have)

**Get all books and their editions:**

```bash
curl "http://localhost:8080/books"
```

Example response:

```json
{
  "books": [
    {
      "book_id": "uuid-here",
      "title": "Introduction to Algorithms",
      "author": "Cormen et al.",
      "editions": [
        { "edition_id": "uuid-1", "edition_name": "2015", "publication_year": 2015 },
        { "edition_id": "uuid-2", "edition_name": "2021", "publication_year": 2021 }
      ]
    }
  ]
}
```

Save **book_id** and **edition_id** values for search and compare.

**List sections of a book or edition:**

```bash
# All sections for one edition
curl "http://localhost:8080/books/sections?edition_id=YOUR_EDITION_UUID"

# All sections for a book (all editions)
curl "http://localhost:8080/books/sections?book_id=YOUR_BOOK_UUID"
```

---

## 3. Search across books and editions

**Semantic search** (finds sections by meaning):

```bash
curl -X POST "http://localhost:8080/search" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "how does quicksort work",
    "limit": 10
  }'
```

Optional filters:

- **book_id**: Restrict to one book
- **edition_id**: Restrict to one edition

---

## 4. Compare two different versions (editions)

Use this when you want the **same section** (e.g. Chapter 5, Section 2) from **two or more editions** side by side.

### By chapter and section numbers

If your document has clear chapter/section structure:

```bash
curl -X POST "http://localhost:8080/compare" \
  -H "Content-Type: application/json" \
  -d '{
    "book_id": "YOUR_BOOK_UUID",
    "chapter_number": 5,
    "section_number": 2,
    "edition_ids": ["EDITION_2015_UUID", "EDITION_2021_UUID"]
  }'
```

Response: the same logical section from each edition (content_text, location_path, edition_id).

### By canonical section ID

If you already have a **canonical_section_id** (e.g. from a previous search or from `/books/sections`):

```bash
curl -X POST "http://localhost:8080/compare" \
  -H "Content-Type: application/json" \
  -d '{
    "book_id": "YOUR_BOOK_UUID",
    "canonical_section_id": "book_xxxx_ch05_sec02",
    "edition_ids": ["EDITION_2015_UUID", "EDITION_2021_UUID"]
  }'
```

### Natural-language query (agent pipeline)

Ask in plain language; the system will plan retrieval and compare/summarize:

```bash
curl -X POST "http://localhost:8080/query" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Compare Chapter 5 Section 2 between the 2015 and 2021 editions"
  }'
```

Other examples:

- *"Summarize how this topic evolved across editions"*
- *"Which edition explains this concept most clearly?"*
- *"Give me a neutral summary of this section from all editions"*

---

## 5. Summarize one section or differences

**Summarize a single section** (by section ID from search or sections list):

```bash
curl -X POST "http://localhost:8080/summarize" \
  -H "Content-Type: application/json" \
  -d '{
    "section_ids": ["SECTION_UUID"],
    "max_length": 300
  }'
```

**Summarize differences between two (or more) sections** (e.g. same section from two editions):

```bash
curl -X POST "http://localhost:8080/summarize" \
  -H "Content-Type: application/json" \
  -d '{
    "section_ids": ["SECTION_UUID_2015", "SECTION_UUID_2021"],
    "max_length": 500
  }'
```

---

## End-to-end flow (summary)

| Step | Action | Endpoint / Tool |
|------|--------|------------------|
| 1 | Upload first version | **POST /upload/document** (file + title, author, edition_name) |
| 2 | Upload second version | **POST /upload/document** (same title/author, different edition_name) |
| 3 | Get book and edition IDs | **GET /books** |
| 4 | Search by topic | **POST /search** (query, optional book_id/edition_id) |
| 5 | Compare same section across editions | **POST /compare** (book_id + chapter/section or canonical_section_id + edition_ids) |
| 6 | Ask in natural language | **POST /query** (e.g. “Compare Chapter 5 Section 2 between 2015 and 2021”) |
| 7 | Summarize one or compare differences | **POST /summarize** (section_ids) |

All responses that return content include **citations** (book, edition, section) so answers stay fact-grounded.
