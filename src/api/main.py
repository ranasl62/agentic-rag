# Main FastAPI app — search, compare, summarize, upload, query pipeline.
# Phases 1–6: auth, rate limit, cache, async ingest, metrics. See docs/DEPLOYMENT.md.
import os
from contextlib import asynccontextmanager
from pathlib import Path

from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Depends, FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware

from src.api.auth import TenantInfo, get_current_tenant
from src.api.cache import get_query_cached, set_query_cached
from src.api.metrics import get_metrics_bytes, get_metrics_content_type
from src.api.middleware.request_metrics_logging import request_metrics_logging_middleware
from src.api.rate_limit import RateLimitExceeded, rate_limit_dependency, rate_limit_response
from src.storage.postgres_client import init_db, ensure_default_tenant
from config import get_settings
from src.storage.qdrant_client import get_qdrant_storage
from src.api.routes import search_router, compare_router, summarize_router, books_router, documents_router
from src.api.routes.upload import router as upload_router
from src.api.routes.ingest import router as ingest_router
from src.api.routes.debug import router as debug_router
from src.api.dependencies import get_orchestrator
from src.api.schemas import QueryRequest, QueryResponse
from src.utils.logging_config import configure_structlog

APP_VERSION = "1.0.0"


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_structlog()
    await init_db()
    await ensure_default_tenant()
    qdrant = get_qdrant_storage()
    qdrant.ensure_collections(vector_size=get_settings().embed_dimension)
    yield
    # TODO: explicit close for pg/qdrant if we ever need graceful shutdown


OPENAPI_TAGS = [
    {"name": "query", "description": "Full agentic pipeline (understand → plan → tools → verify)."},
    {"name": "search", "description": "Vector and section search."},
    {"name": "compare", "description": "Compare sections across editions."},
    {"name": "summarize", "description": "Summarize sections or differences."},
    {"name": "books", "description": "List books, editions, sections (legacy)."},
    {"name": "documents", "description": "List documents, editions, sections."},
    {"name": "upload", "description": "Upload documents (sync or async)."},
    {"name": "ingest", "description": "Ingestion status and jobs."},
    {"name": "debug", "description": "Debug and development endpoints."},
    {"name": "ops", "description": "Health, info, and Prometheus metrics."},
]

app = FastAPI(
    title="Agentic RAG API",
    description="Multi-edition book search, compare, and summarize with tool-based agents. Production stack: tenant auth, rate limiting, caching, async ingest, metrics.",
    version=APP_VERSION,
    lifespan=lifespan,
    openapi_tags=OPENAPI_TAGS,
)
# CORS: with allow_credentials=True the browser forbids allow_origins=["*"]. List origins or use regex.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:3002",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
        "http://127.0.0.1:3002",
        "http://0.0.0.0:3000",
        "http://0.0.0.0:3001",
        "http://0.0.0.0:3002",
    ],
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1|0\.0\.0\.0)(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)
app.add_middleware(BaseHTTPMiddleware, dispatch=request_metrics_logging_middleware)  # Phase 6: metrics + logging
app.add_exception_handler(RateLimitExceeded, lambda req, exc: rate_limit_response(exc))

app.include_router(search_router)
app.include_router(compare_router)
app.include_router(summarize_router)
app.include_router(books_router)
app.include_router(documents_router)
app.include_router(upload_router)
app.include_router(ingest_router)
app.include_router(debug_router)


@app.get("/", tags=["ops"])
async def root():
    """Redirect to API info and docs."""
    return {"app": "Agentic RAG API", "docs": "/docs", "health": "/health", "info": "/info"}


def _env_file_values() -> dict:
    """Read .env from project root into a dict (no process env change)."""
    try:
        from dotenv import dotenv_values
        root = Path(__file__).resolve().parent.parent.parent
        env_path = root / ".env"
        if env_path.is_file():
            return dotenv_values(env_path) or {}
    except Exception:
        pass
    return {}


@app.get("/info", tags=["ops"])
async def info():
    """API name, version, and feature flags for operators."""
    s = get_settings()
    env_file = _env_file_values()
    # 1) Process env 2) .env on disk 3) cached settings (so UI reflects .env when possible)
    provider = (
        (os.environ.get("CHAT_PROVIDER") or env_file.get("CHAT_PROVIDER") or s.chat_provider or "ollama")
    ).strip().lower()
    provider_label = {"openai": "OpenAI", "anthropic": "Anthropic"}.get(provider, provider.capitalize())
    # Model name for search answer: match the provider we're returning
    if provider == "openai":
        search_model = (os.environ.get("OPENAI_CHAT_MODEL") or env_file.get("OPENAI_CHAT_MODEL") or s.openai_chat_model or "gpt-4o-mini").strip()
    elif provider == "anthropic":
        search_model = (os.environ.get("ANTHROPIC_CHAT_MODEL") or env_file.get("ANTHROPIC_CHAT_MODEL") or s.anthropic_chat_model or "claude-3-5-sonnet-20241022").strip()
    else:
        search_model = s.chat_model_for("search_answer")
    return {
        "app": "Agentic RAG API",
        "version": APP_VERSION,
        "auth_required": s.require_auth,
        "metrics_enabled": s.metrics_enabled,
        "chat_provider": provider,
        "chat_provider_label": provider_label,
        "search_answer_model": search_model,
    }


@app.post("/query", response_model=QueryResponse, tags=["query"])
async def query(
    body: QueryRequest,
    tenant: TenantInfo = Depends(get_current_tenant),
    _=Depends(rate_limit_dependency("query")),
):
    """Full agentic pipeline: understand query → plan → tools → compare/summarize → verify."""
    if not body.skip_cache:
        cached = await get_query_cached(tenant.tenant_id, body.query)
        if cached is not None:
            return QueryResponse.model_validate(cached)

    orchestrator = get_orchestrator()
    result = await orchestrator.run(
        query=body.query,
        skip_verification=body.skip_verification,
        tenant_id=tenant.tenant_id,
    )
    response = QueryResponse(
        response=result["response"],
        steps=result.get("steps", []),
        citations=result.get("citations", []),
        verified=result.get("verified", False),
    )
    if not body.skip_cache:
        await set_query_cached(tenant.tenant_id, body.query, response.model_dump())
    return response


@app.get("/health", tags=["ops"])
async def health():
    """Liveness/readiness for load balancers and k8s."""
    return {"status": "ok", "version": APP_VERSION}


@app.get("/metrics", tags=["ops"])
async def metrics():
    """Phase 6: Prometheus metrics. No auth. Returns 404 if METRICS_ENABLED=false."""
    if not get_settings().metrics_enabled:
        return Response(status_code=404)
    return Response(
        content=get_metrics_bytes(),
        media_type=get_metrics_content_type(),
    )
