# Main FastAPI app — search, compare, summarize, upload, query pipeline.
# Phases 1–6: auth, rate limit, cache, async ingest, metrics. See docs/PRODUCTION_ROADMAP_60K.md.
from contextlib import asynccontextmanager

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
from src.api.routes import search_router, compare_router, summarize_router, books_router
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
    {"name": "books", "description": "List books, editions, sections."},
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
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(BaseHTTPMiddleware, dispatch=request_metrics_logging_middleware)  # Phase 6: metrics + logging
app.add_exception_handler(RateLimitExceeded, lambda req, exc: rate_limit_response(exc))

app.include_router(search_router)
app.include_router(compare_router)
app.include_router(summarize_router)
app.include_router(books_router)
app.include_router(upload_router)
app.include_router(ingest_router)
app.include_router(debug_router)


@app.get("/", tags=["ops"])
async def root():
    """Redirect to API info and docs."""
    return {"app": "Agentic RAG API", "docs": "/docs", "health": "/health", "info": "/info"}


@app.get("/info", tags=["ops"])
async def info():
    """API name, version, and feature flags for operators."""
    s = get_settings()
    return {
        "app": "Agentic RAG API",
        "version": APP_VERSION,
        "auth_required": s.require_auth,
        "metrics_enabled": s.metrics_enabled,
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
