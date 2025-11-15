"""
Run ingestion in an async context. Used by Celery task via asyncio.run().
"""
from __future__ import annotations

import asyncio
from uuid import UUID

from config import get_settings
from src.storage.postgres_client import session_scope
from src.storage.qdrant_client import get_qdrant_storage
from src.llm.embeddings import get_embedding_service
from src.ingestion.ingestion_pipeline import IngestionPipeline


async def run_ingest(
    tenant_id: UUID,
    title: str,
    author: str,
    edition_name: str,
    raw_text: str,
    publication_year: int | None = None,
) -> int:
    """
    Run full ingestion; returns number of sections created.
    Raises on failure.
    """
    get_qdrant_storage().ensure_collections(vector_size=get_settings().embed_dimension)
    async with session_scope() as session:
        pipeline = IngestionPipeline(
            session,
            get_qdrant_storage(),
            get_embedding_service(),
        )
        sections = await pipeline.ingest_raw_text(
            tenant_id=tenant_id,
            title=title,
            author=author,
            edition_name=edition_name,
            raw_text=raw_text,
            publication_year=publication_year,
        )
    return len(sections)
