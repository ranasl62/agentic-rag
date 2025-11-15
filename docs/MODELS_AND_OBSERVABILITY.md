# Model Configuration & Optional LangChain / LangSmith

## 1. Per-task Ollama models (built-in)

You can use **one model for everything** or **different models per task**. Change anytime via env (restart API to apply).

| Task | Env var | Default | Use case |
|------|---------|---------|----------|
| **Embeddings** | `OLLAMA_EMBED_MODEL` | nomic-embed-text | Vector search; keep fixed for index compatibility. |
| **Search answer** | `OLLAMA_SEARCH_ANSWER_MODEL` | `OLLAMA_CHAT_MODEL` | "Generate answer" in Search tab. |
| **Query pipeline** | `OLLAMA_QUERY_MODEL` | `OLLAMA_CHAT_MODEL` | Query understanding, retrieval planning, section matching. |
| **Summarize** | `OLLAMA_SUMMARIZE_MODEL` | `OLLAMA_CHAT_MODEL` | Summarization agent and summarize endpoint. |
| **Compare** | `OLLAMA_COMPARE_MODEL` | `OLLAMA_CHAT_MODEL` | Comparison agent. |
| **Verify** | `OLLAMA_VERIFY_MODEL` | `OLLAMA_CHAT_MODEL` | Verification (groundedness) agent. |

Example: use a small model for planning and a larger one for answers:

```env
OLLAMA_CHAT_MODEL=llama3.2
OLLAMA_QUERY_MODEL=phi3
OLLAMA_SEARCH_ANSWER_MODEL=llama3.2
OLLAMA_SUMMARIZE_MODEL=llama3.2
OLLAMA_COMPARE_MODEL=llama3.2
```

### Recommended Ollama models (as of 2024)

- **Embeddings:** `nomic-embed-text` (default); alternatives: `mxbai-embed-large`, `all-minilm`.
- **Chat (general):** `llama3.2`, `llama3.1`, `mistral`, `phi3`; smaller/faster: `phi3:mini`, `tinyllama`.
- **Summarize / Compare:** Same as chat; use a capable model for coherence.
- **Query (planning):** Can use a smaller model (e.g. `phi3`) to save latency if you prefer.

Pull what you need: `ollama pull <model>` (or `docker exec ollama ollama pull <model>` if Ollama runs in Docker).

---

## 2. Changing models anytime

- **Today:** Edit `.env` (or set env in Docker), then restart the API:  
  `docker compose up -d api-service`
- **No code change** is required; all model names are read from settings at request time.
- **Future:** You could add an admin API or config reload endpoint to switch models without restart (same `ollama_model_for()` would be used with updated config).

---

## 3. Optional: LangChain / LangGraph

The current stack uses a **custom orchestrator** and **direct Ollama HTTP** for chat and embeddings. You can keep this and still **swap models via env** as above.

If you want to adopt **LangChain** and **LangGraph**:

- **LangChain** can provide:
  - **Model abstraction:** `ChatOllama`, `OllamaEmbeddings` so you can swap to OpenAI/Anthropic later by changing the class.
  - **Prompt management:** `ChatPromptTemplate`, `MessagesPlaceholder` in code or loaded from files.
  - **Chains:** Compose retrieval + prompt + LLM in a chain (e.g. for “search then answer”).
- **LangGraph** can provide:
  - **Orchestrator as a graph:** Nodes = query understanding, retrieval, compare, summarize; edges = conditional routing. State is passed along the graph.
  - **Cycles and human-in-the-loop:** e.g. “refine answer” loops, approval steps.

**Integration options:**

1. **Thin wrapper:** Keep current API and tools; replace `OllamaClient` / `EmbeddingService` with LangChain’s `ChatOllama` and `OllamaEmbeddings`. Model names still come from your config (e.g. `ollama_model_for("query")`). No LangGraph yet.
2. **Orchestrator in LangGraph:** Implement the same flow (query → plan → tools → compare/summarize) as a LangGraph state machine. Tools stay as-is (search_sections, etc.); only the “brain” (which tool to call, when to compare/summarize) moves into the graph. Models still configurable via env and LangChain’s model kwargs.
3. **Full LangChain RAG:** Use LC’s document loaders, text splitters, and vector-store abstraction; keep Qdrant as the vector store backend. More refactor; only do this if you want to standardize on LC’s patterns.

If you add LangChain, pin versions (e.g. `langchain-core`, `langchain-ollama`, `langgraph`) in `requirements.txt` and keep the existing config so **model selection still goes through your env** (e.g. pass `ollama_model_for("query")` into `ChatOllama(model=...)`).

---

## 4. LangSmith (local / self-hosted)

**LangSmith** is used for tracing and debugging LLM runs (prompts, responses, latency, errors). You can use it **locally** in two ways:

### Option A: LangSmith Cloud (no local server)

- Sign up at [smith.langchain.com](https://smith.langchain.com).
- Create an API key and a project.
- In `.env`:
  ```env
  LANGCHAIN_TRACING_V2=true
  LANGCHAIN_ENDPOINT=https://api.smith.langchain.com
  LANGCHAIN_API_KEY=<your-key>
  LANGCHAIN_PROJECT=local-ai-agent
  ```
- If you later use **LangChain** in the app, the LangChain/LangGraph calls will auto-send traces to LangSmith. For the **current custom Ollama client**, traces are not sent unless you add OpenTelemetry or LangSmith’s SDK and instrument the HTTP calls yourself.

### Option B: LangSmith server (self-hosted / local)

- LangSmith server can be run locally (e.g. Docker) so all data stays on your machine.
- See [LangSmith self-hosted docs](https://docs.smith.langchain.com/self_hosted) for setup.
- Then set in `.env`:
  ```env
  LANGCHAIN_TRACING_V2=true
  LANGCHAIN_ENDPOINT=http://localhost:1984
  LANGCHAIN_API_KEY=optional-for-local
  LANGCHAIN_PROJECT=local-ai-agent
  ```

### Making the current app send traces to LangSmith

- **With LangChain:** Once you use `ChatOllama` / `OllamaEmbeddings` and the above env vars, LangChain will report runs to LangSmith.
- **Without LangChain:** You’d add a thin instrumentation layer (e.g. OpenTelemetry with a LangSmith exporter, or manual span creation) around `OllamaClient.chat()` and `EmbeddingService.embed()` so that each call is logged as a span. That way you can see prompts, model names, and latency in LangSmith even before adopting LangChain.

### Optional: LangSmith in Docker Compose

If a LangSmith server image is available for self-hosted, you can add it under a profile, for example:

```yaml
# Example; image and config depend on LangSmith self-hosted availability
  langsmith:
    image: langsmith/server:latest   # check actual image name
    profiles:
      - with-langsmith
    ports:
      - "1984:1984"
    environment:
      - LANGCHAIN_ENDPOINT=http://localhost:1984
```

Run with: `docker compose --profile with-langsmith up -d`. Then point `LANGCHAIN_ENDPOINT` in the API service to `http://langsmith:1984` when using that profile.

---

## 5. OpenAI and Anthropic (Claude / Opus)

You can use **OpenAI** or **Anthropic** for chat instead of (or alongside) Ollama. Embeddings can also use OpenAI.

### Chat (OpenAI or Anthropic)

Set in `.env`:

**OpenAI (e.g. gpt-4o, gpt-4o-mini):**
```env
CHAT_PROVIDER=openai
OPENAI_API_KEY=sk-your-key
OPENAI_CHAT_MODEL=gpt-4o-mini
# Optional: Azure or other compatible API
# OPENAI_BASE_URL=https://your-resource.openai.azure.com/openai/deployments/your-deploy
```

**Anthropic (e.g. Claude 3.5 Sonnet, Claude 3 Opus):**
```env
CHAT_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-your-key
ANTHROPIC_CHAT_MODEL=claude-3-5-sonnet-20241022
# Or: claude-3-opus-20240229
```

All chat tasks (query, search answer, summarize, compare, verify) then use the chosen provider. Restart the API after changing.

### Embeddings (OpenAI)

To use OpenAI embeddings (e.g. `text-embedding-3-small`, 1536 dimensions):

```env
EMBED_PROVIDER=openai
OPENAI_API_KEY=sk-your-key
OPENAI_EMBED_MODEL=text-embedding-3-small
```

**Important:** OpenAI embeddings are 1536-dimensional; Ollama (nomic-embed-text) is 768. If you switch from Ollama to OpenAI (or the other way around), you must **re-ingest** your documents so the vector store matches the new dimension. Existing 768-dim points cannot be used in a 1536-dim collection.

---

## 6. Summary

| Goal | Approach |
|------|----------|
| **Different model per task** | Use `OLLAMA_*_MODEL` env vars; change anytime, restart API. |
| **Best-fit Ollama models** | Embeddings: nomic-embed-text; Chat: llama3.2 / mistral / phi3; optional smaller model for query planning. |
| **Change model anytime** | Env-based config; no code change; restart to apply. |
| **Add LangChain/LangGraph** | Optional: wrap Ollama with LC, then move orchestrator to LangGraph; keep your tools and config. |
| **LangSmith local** | Use LangSmith Cloud or self-hosted server; set `LANGCHAIN_*` env; add LC or custom instrumentation to send traces. |
| **OpenAI / Anthropic** | Set `CHAT_PROVIDER=openai` or `anthropic` and the corresponding API key and model; restart API. |
| **OpenAI embeddings** | Set `EMBED_PROVIDER=openai`; re-ingest after switching (different vector dimension). |
