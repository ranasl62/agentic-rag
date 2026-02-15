# Agentic RAG — System Design Diagram

High-level architecture, components, and main flows. Render the Mermaid blocks in GitHub, VS Code, or [Mermaid Live](https://mermaid.live).

---

## 1. System overview (components)

```mermaid
flowchart TB
    subgraph Client["Client layer"]
        Browser["Web UI (Next.js)\n:3002"]
    end

    subgraph Gateway["Gateway"]
        Nginx["Nginx\n:8080"]
    end

    subgraph API["API layer"]
        FastAPI["FastAPI\nAuth · Rate limit · Cache · CORS"]
        Routes["Routes\n/search, /query, /upload,\n/compare, /summarize, /books,\n/documents, /ingest"]
        FastAPI --> Routes
    end

    subgraph Agents["Agent layer"]
        Orch["Orchestrator"]
        QUA["Query understanding"]
        RPA["Retrieval planning"]
        CompA["Comparison agent"]
        SumA["Summarization agent"]
        VerA["Verification agent"]
        Orch --> QUA
        Orch --> RPA
        Orch --> CompA
        Orch --> SumA
        Orch --> VerA
    end

    subgraph Tools["Tools"]
        SearchT["search_sections"]
        FindSame["find_same_section_across_editions"]
        ListEd["list_available_editions"]
        MatchT["match_sections"]
        CompareT["compare_sections"]
        SumSec["summarize_section"]
        SumDiff["summarize_differences"]
    end

    subgraph Storage["Storage"]
        Postgres[("PostgreSQL\n(PgBouncer)\nBooks, Editions,\nSections, Tenants")]
        Qdrant[("Qdrant\nVectors\n(sections/chunks)")]
        Redis[("Redis\nCache · Rate limit\nCelery broker")]
    end

    subgraph Workers["Workers"]
        Celery["Celery worker\nAsync ingestion"]
    end

    subgraph LLM["LLM (configurable)"]
        Chat["Chat\nOllama / OpenAI / Anthropic"]
        Embed["Embeddings\nOllama / OpenAI"]
    end

    Browser -->|HTTP + X-API-Key| Nginx
    Nginx --> FastAPI
    Routes --> Orch
    Routes --> SearchT
    Routes --> CompareT
    Routes --> SumSec
    Orch --> Tools
    Tools --> Postgres
    Tools --> Qdrant
    Tools --> Chat
    Tools --> Embed
    FastAPI --> Redis
    FastAPI --> Postgres
    FastAPI --> Celery
    Celery --> Postgres
    Celery --> Qdrant
    Celery --> Embed
```

---

## 2. Deployment (Docker)

```mermaid
flowchart LR
    subgraph Host["Host"]
        subgraph Docker["Docker Compose"]
            N["Nginx\n:8080"]
            A["api-service\n:8000"]
            C["Celery worker"]
            P["Postgres\n:5433"]
            Q["Qdrant\n:6333"]
            R["Redis\n:6379"]
            B["PgBouncer"]
            W["Web (Next.js)\n:3002→3000"]
        end
    end

    User["User"] -->|8080| N
    User -->|3002| W
    N --> A
    W -->|NEXT_PUBLIC_API_URL| N
    A --> B
    A --> Q
    A --> R
    C --> B
    C --> Q
    C --> R
    B --> P
```

---

## 3. Query pipeline (POST /query)

Natural-language question → understand intent → plan retrieval → run tools → compare/summarize → verify → response.

```mermaid
sequenceDiagram
    participant Client
    participant API
    participant Orch as Orchestrator
    participant QUA as Query understanding
    participant RPA as Retrieval planning
    participant Tools
    participant PG as Postgres
    participant Qdrant
    participant LLM

    Client->>API: POST /query { query }
    API->>API: Auth (X-API-Key) · rate limit · cache?
    API->>Orch: run(query, tenant_id)

    Orch->>Tools: list_available_editions
    Tools->>PG: books, editions
    PG-->>Orch: available_books

    Orch->>QUA: run(query, available_books)
    QUA->>LLM: chat (intent, book_ids?)
    LLM-->>Orch: intent

    Orch->>RPA: run(query, intent)
    RPA->>LLM: chat (plan: which tools, params)
    LLM-->>Orch: plan

    loop Tool steps
        Orch->>Tools: search_sections | find_same_section | match_sections | ...
        Tools->>Qdrant: vector search
        Tools->>PG: sections, metadata
        Qdrant-->>Tools: hits
        PG-->>Tools: content
        Tools-->>Orch: ToolResult
    end

    Orch->>LLM: comparison / summarization agents
    LLM-->>Orch: comparison or summary text

    Orch->>LLM: verification agent (grounded?)
    LLM-->>Orch: verified

    Orch-->>API: response, steps, citations
    API-->>Client: QueryResponse
```

---

## 4. Upload and ingestion

Document (PDF/TXT) → parse → structure → chunk → embed → store in Postgres + Qdrant. Sync or async (Celery).

```mermaid
flowchart LR
    subgraph Upload["Upload"]
        UI["Web UI"] -->|POST /upload/document| API["FastAPI"]
        API -->|sync| Pipe["IngestionPipeline"]
        API -->|async_mode=1| RedisQ["Redis queue"]
    end

    subgraph Ingest["Ingestion pipeline"]
        Pipe --> Parse["Structure extractor\n(book/edition/chapter/section)"]
        Parse --> Chunk["Semantic chunker"]
        Chunk --> Embed["Embedding service"]
        Embed --> PG[("Postgres\nSections, metadata")]
        Embed --> Qdrant[("Qdrant\nVectors + payload")]
    end

    subgraph Async["Async path"]
        RedisQ --> Celery["Celery worker"]
        Celery --> Pipe
    end

    API -->|202 + job_id| UI
    API -->|GET /ingest/status/:id| UI
```

---

## 5. Search flow (POST /search)

Direct vector search with optional LLM-generated answer.

```mermaid
flowchart LR
    Client["Client"] -->|POST /search| API["FastAPI"]
    API --> Auth["Auth · rate limit"]
    Auth --> Cache{"Cache hit?"}
    Cache -->|yes| Response["SearchResponse"]
    Cache -->|no| Embed["Embed query"]
    Embed --> Qdrant["Qdrant search"]
    Qdrant --> Postgres["Load full section text\nif include_content"]
    Postgres --> Items["Result items"]
    Items --> LLM{"generate_answer?"}
    LLM -->|yes| Chat["Chat (answer from top results)"]
    LLM -->|no| Response
    Chat --> Response
    Response --> Cache
```

---

## 6. Data model (simplified)

```mermaid
erDiagram
    Tenant ||--o{ Book : has
    Book ||--o{ Edition : has
    Edition ||--o{ Section : has
    Section ||--o{ SectionChunk : has

    Tenant {
        uuid tenant_id PK
        string name
        string slug
        string api_key_hash
    }

    Book {
        uuid book_id PK
        uuid tenant_id FK
        string title
        string author
    }

    Edition {
        uuid edition_id PK
        uuid book_id FK
        string edition_name
    }

    Section {
        uuid section_id PK
        uuid edition_id FK
        string content_text
        string location_path
    }

    SectionChunk {
        uuid chunk_id PK
        uuid section_id FK
        vector embedding
    }
```

---

## 7. Config / env (main knobs)

| Layer    | Env / config |
|----------|----------------|
| **API**  | `API_PORT`, `REQUIRE_AUTH`, rate limits, cache TTL |
| **Chat** | `CHAT_PROVIDER` (ollama / openai / anthropic), `OPENAI_API_KEY`, etc. |
| **Embed**| `EMBED_PROVIDER` (ollama / openai), `OPENAI_EMBED_MODEL` |
| **DB**   | `POSTGRES_*`, PgBouncer in Docker |
| **Vector** | `QDRANT_*`, embedding dimension from embed provider |
| **Frontend** | `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_AGENT_API_KEY` |

For more detail see [ARCHITECTURE_AND_DESIGN.md](ARCHITECTURE_AND_DESIGN.md), [GETTING_STARTED.md](GETTING_STARTED.md), and [.env.example](../.env.example).
