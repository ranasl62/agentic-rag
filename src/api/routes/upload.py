"""
Document upload and ingest: users upload a file (text or PDF) as one edition of a book.
Phase 3: optional async mode (async=1) returns 202 + job_id; poll GET /ingest/status/{job_id}.
"""
import uuid
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from config import get_settings
from src.api.auth import TenantInfo, get_current_tenant
from src.api.rate_limit import rate_limit_dependency
from src.storage.postgres_client import session_scope
from src.storage.qdrant_client import get_qdrant_storage
from src.llm.embeddings import get_embedding_service
from src.ingestion.ingestion_pipeline import IngestionPipeline
from src.worker.celery_app import ingest_document_task, set_job_status

router = APIRouter(prefix="/upload", tags=["upload"])


def _extract_text_from_pdf(content: bytes) -> str:
    """Extract plain text from PDF bytes."""
    try:
        from pypdf import PdfReader
        import io
        reader = PdfReader(io.BytesIO(content))
        parts = []
        for page in reader.pages:
            parts.append(page.extract_text() or "")
        return "\n\n".join(parts)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"PDF extraction failed: {e}")


def _parse_async_mode(value: Optional[str]) -> bool:
    if value is None:
        return get_settings().ingest_async_default
    return str(value).strip().lower() in ("1", "true", "yes")


@router.post("/document")
async def upload_document(
    file: UploadFile = File(...),
    title: str = Form(...),
    author: str = Form(...),
    edition_name: str = Form(..., description="e.g. '2021' or 'First Edition'"),
    publication_year: Optional[int] = Form(None),
    async_mode: Optional[str] = Form(None, description="Set to 1 or true for async (202 + job_id)"),
    tenant: TenantInfo = Depends(get_current_tenant),
    _=Depends(rate_limit_dependency("upload")),
):
    """
    Upload a document as one edition of a book.
    - **.txt**: ingested as plain text.
    - **.pdf**: text is extracted and then ingested.
    - **async_mode=1**: enqueue ingestion, return 202 with job_id; poll GET /ingest/status/{job_id}.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")
    raw = await file.read()
    if len(raw) == 0:
        raise HTTPException(status_code=400, detail="File is empty")

    suffix = (file.filename or "").lower().split(".")[-1]
    if suffix == "txt":
        try:
            text = raw.decode("utf-8", errors="replace")
        except Exception:
            text = raw.decode("latin-1", errors="replace")
    elif suffix == "pdf":
        text = _extract_text_from_pdf(raw)
    else:
        raise HTTPException(
            status_code=400,
            detail="Only .txt and .pdf are supported. Use a .txt or .pdf file.",
        )

    use_async = _parse_async_mode(async_mode)
    if use_async:
        job_id = str(uuid.uuid4())
        from datetime import datetime, timezone
        set_job_status(job_id, "pending", created_at=datetime.now(timezone.utc).isoformat())
        ingest_document_task.delay(
            job_id=job_id,
            tenant_id=str(tenant.tenant_id),
            raw_text=text,
            title=title.strip(),
            author=author.strip(),
            edition_name=edition_name.strip(),
            publication_year=publication_year,
        )
        return JSONResponse(
            status_code=202,
            content={
                "job_id": job_id,
                "message": "Ingestion started. Poll GET /ingest/status/{job_id} for status.",
                "status_url": f"/ingest/status/{job_id}",
            },
        )

    qdrant = get_qdrant_storage()
    qdrant.ensure_collections(vector_size=get_settings().embed_dimension)
    embedding = get_embedding_service()

    try:
        async with session_scope() as sess:
            pipeline = IngestionPipeline(sess, qdrant, embedding)
            sections = await pipeline.ingest_raw_text(
                tenant_id=tenant.tenant_id,
                title=title.strip(),
                author=author.strip(),
                edition_name=edition_name.strip(),
                raw_text=text,
                publication_year=publication_year,
            )
    except httpx.ConnectError as e:
        raise HTTPException(
            status_code=503,
            detail=(
                "Ollama is not reachable (connection refused). "
                "Upload needs embeddings. Ensure Ollama is running on the host and reachable from Docker, "
                "or start the Ollama container: docker compose --profile with-ollama up -d and set OLLAMA_HOST=http://ollama in .env"
            ),
        ) from e
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            raise HTTPException(
                status_code=503,
                detail=(
                    "Ollama embedding model not found (404). "
                    "Pull the model on the host, e.g.: ollama pull nomic-embed-text (or set OLLAMA_EMBED_MODEL to a model you have)."
                ),
            ) from e
        raise HTTPException(status_code=502, detail=f"Ollama error: {e.response.status_code}") from e

    return {
        "success": True,
        "message": f"Ingested {len(sections)} sections.",
        "title": title,
        "author": author,
        "edition_name": edition_name,
        "sections_count": len(sections),
    }
