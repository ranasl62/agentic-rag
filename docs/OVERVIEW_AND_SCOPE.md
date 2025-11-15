# Overview & Scope

What the Agentic RAG system is, what problem it solves, and what you can do with it.

---

## What problem does this solve?

Many teams have **large collections of documents**—manuals, books, reports, articles, specifications—and need to:

- **Find** relevant content quickly using natural language, not just keywords.
- **Compare** the same topic or section across different versions (e.g. 2015 vs 2021 edition, draft vs final).
- **Summarize** long sections or differences between versions with answers grounded in the actual text.

Doing this manually is slow and error-prone. A generic keyword search does not understand “the same section in another edition” or “how did this change between versions?” This system is a **RAG (Retrieval-Augmented Generation)** application that:

1. **Ingests** your documents (any supported format), structures them into books, editions, and sections, and builds a searchable vector index.
2. **Exposes** search, compare, and summarize over an API (and optional web UI).
3. **Uses tool-based agents** to interpret questions, plan retrieval, match sections across editions, and produce answers with citations.

You get **semantic search**, **edition-aware comparison**, and **summarization** with strict grounding in your ingested content.

---

## Scope: what kind of documents can I use?

**You can feed any kind of document** into the system. It is **not** limited to repair manuals or a single domain.

| Aspect | Scope |
|--------|--------|
| **Formats** | **PDF** and **plain text (TXT)**. PDFs are converted to text; then the same pipeline runs as for TXT. |
| **Content type** | Books, manuals, reports, articles, specifications, policies, guides, whitepapers, technical docs—anything with structure you want to search or compare. |
| **Structure** | The pipeline detects **chapters and sections** from headings. If your doc has clear headings (e.g. `## Chapter 3`, `### Section 2.1`), they are used to build a stable structure and “same section across editions” matching. Less structured docs are still ingested and chunked for search. |
| **Multi-edition** | Upload the same logical “book” multiple times with different **edition names** (e.g. `2015`, `2021`, `Draft v2`). The system tracks editions and can compare “the same section” across them. |
| **Multi-tenant** | In production, data is scoped by **tenant** (e.g. per customer or brand). Each tenant only sees and searches their own documents. |

So: **any domain, any document type** that you can provide as PDF or TXT will work. The system does not assume repair manuals; it assumes “documents with optional chapter/section structure and optional multiple editions.”

Optional future extensions (see [Document scope and vehicle metadata](DOCUMENT_SCOPE_AND_VEHICLE_METADATA.md)) add filters like country, brand, language, and vehicle metadata with wildcards—useful for manuals but not required for general use.

---

## What can users do?

| Capability | Description |
|------------|-------------|
| **Search** | Natural-language or keyword search over all ingested content. Returns matching sections with scores. Filter by book, edition, or tenant. |
| **Compare** | “Compare section X between edition A and edition B.” Retrieves the same logical section in each edition and returns a side-by-side or diff-style comparison (and optional LLM summary of differences). |
| **Summarize** | Summarize one or more sections, or “summarize how this topic changed across editions.” Answers are grounded in retrieved text with citations. |
| **Full pipeline (query)** | Ask a single question in natural language (e.g. “Compare Chapter 5 Section 2 between 2015 and 2021 editions”). The orchestrator runs query understanding, retrieval planning, tools (search, match, compare, summarize), and optional verification. |
| **Chat** | Interactive chat (script or UI) that sends each message through the `/query` pipeline so users can explore and refine questions. |

All of this works over the **API** (curl, Swagger at `/docs`, or your own app) and optionally a **Next.js web UI**.

---

## Who is this for?

- **End users** (analysts, support, legal, product): Upload documents, search, compare editions, get summaries. Use the [User guide](USER_GUIDE.md) and API/UI.
- **Developers**: Integrate the API into your app, run locally, extend tools/agents. Use [Architecture & design](ARCHITECTURE_AND_DESIGN.md), [Developer guide](DEVELOPER_GUIDE.md), and [API reference](api_reference.md).
- **Operators / DevOps**: Deploy and run at scale (auth, rate limits, cache, async ingest, scaling, monitoring). Use [Production roadmap](PRODUCTION_ROADMAP_60K.md) and [Runbooks](runbooks/).

---

## Where to go next

- **I want to use the system** → [User guide](USER_GUIDE.md)  
- **I want to understand how it’s built** → [Architecture & design](ARCHITECTURE_AND_DESIGN.md)  
- **I want to develop or extend it** → [Developer guide](DEVELOPER_GUIDE.md)  
- **I want to test it** → [Testing guide](TESTING_GUIDE.md)  
- **I want to run it in production** → [Production roadmap](PRODUCTION_ROADMAP_60K.md) and [Runbooks](runbooks/)
