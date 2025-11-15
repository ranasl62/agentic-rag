"""
Ingest job status (Phase 3). GET /ingest/status/{job_id} to poll async upload result.
"""
from fastapi import APIRouter, HTTPException

from src.worker.celery_app import get_job_status

router = APIRouter(prefix="/ingest", tags=["ingest"])


@router.get("/status/{job_id}")
async def get_ingest_status(job_id: str):
    """
    Get status of an async ingestion job.
    Returns 404 if job not found or expired.
    """
    data = get_job_status(job_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Job not found or expired")
    return data
