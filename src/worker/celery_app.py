"""
Celery app for Phase 3 async ingestion. Broker: Redis.
Run worker: celery -A src.worker.celery_app worker -l info
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from uuid import UUID

import redis
from celery import Celery

from config import get_settings

settings = get_settings()

app = Celery(
    "agentic_rag",
    broker=settings.celery_broker_url_or_redis,
    backend=settings.celery_broker_url_or_redis,
)
app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)

INGEST_JOB_PREFIX = "ingest:job:"


def _job_key(job_id: str) -> str:
    return f"{INGEST_JOB_PREFIX}{job_id}"


def set_job_status(
    job_id: str,
    status: str,
    result: dict | None = None,
    error: str | None = None,
    created_at: str | None = None,
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    payload = {
        "job_id": job_id,
        "status": status,
        "updated_at": now,
    }
    if created_at is not None:
        payload["created_at"] = created_at
    if result is not None:
        payload["result"] = result
    if error is not None:
        payload["error"] = error
    r = redis.from_url(settings.redis_url, decode_responses=True)
    key = _job_key(job_id)
    r.setex(
        key,
        settings.ingest_job_status_ttl_seconds,
        json.dumps(payload),
    )


def get_job_status(job_id: str) -> dict | None:
    r = redis.from_url(settings.redis_url, decode_responses=True)
    raw = r.get(_job_key(job_id))
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


@app.task(bind=True, name="ingest_document")
def ingest_document_task(
    self,
    job_id: str,
    tenant_id: str,
    raw_text: str,
    title: str,
    author: str,
    edition_name: str,
    publication_year: int | None = None,
) -> dict:
    """
    Run ingestion in background. Updates Redis job status.
    """
    set_job_status(job_id, "running")
    try:
        n = asyncio.run(
            _run_ingest(
                tenant_id=UUID(tenant_id),
                title=title,
                author=author,
                edition_name=edition_name,
                raw_text=raw_text,
                publication_year=publication_year,
            )
        )
        result = {"sections_count": n, "message": f"Ingested {n} sections."}
        set_job_status(job_id, "completed", result=result)
        return result
    except Exception as e:
        set_job_status(job_id, "failed", error=str(e))
        raise


async def _run_ingest(
    tenant_id: UUID,
    title: str,
    author: str,
    edition_name: str,
    raw_text: str,
    publication_year: int | None = None,
) -> int:
    from src.worker.ingest_runner import run_ingest
    return await run_ingest(
        tenant_id=tenant_id,
        title=title,
        author=author,
        edition_name=edition_name,
        raw_text=raw_text,
        publication_year=publication_year,
    )
