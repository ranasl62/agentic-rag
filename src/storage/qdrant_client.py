"""
Qdrant vector store client for section and chunk embeddings.
Supports metadata filtering and multi-collection strategy.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from uuid import UUID

from qdrant_client import QdrantClient
from qdrant_client.http import models as qdrant_models
from qdrant_client.http.models import PointStruct, Filter, FieldCondition, MatchValue

from config import get_settings

SECTION_COLLECTION = "section_embeddings"
CHUNK_COLLECTION = "chunk_embeddings"
VECTOR_SIZE = 768


def _point_id_from_uuid(uuid_val: UUID) -> str:
    return str(uuid_val).replace("-", "")


class QdrantStorage:
    """Production Qdrant client with section and chunk collections."""

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        grpc_port: Optional[int] = None,
    ) -> None:
        s = get_settings()
        self._host = host or s.qdrant_host
        self._port = port or s.qdrant_port
        self._grpc_port = grpc_port or s.qdrant_grpc_port
        self._client: Optional[QdrantClient] = None

    @property
    def client(self) -> QdrantClient:
        if self._client is None:
            self._client = QdrantClient(
                host=self._host,
                port=self._port,
                check_compatibility=False,  # Server may be 1.7.x; avoid version warning
            )
        return self._client

    def ensure_collections(self, vector_size: int = VECTOR_SIZE) -> None:
        """Create section and chunk collections if they do not exist."""
        for name in (SECTION_COLLECTION, CHUNK_COLLECTION):
            try:
                self.client.get_collection(name)
            except Exception:
                self.client.create_collection(
                    collection_name=name,
                    vectors_config=qdrant_models.VectorParams(
                        size=vector_size,
                        distance=qdrant_models.Distance.COSINE,
                    ),
                )

    def upsert_section_vector(
        self,
        point_id: str,
        vector: List[float],
        payload: Dict[str, Any],
    ) -> None:
        """Insert or update a section-level vector (e.g. heading or full section)."""
        self.client.upsert(
            collection_name=SECTION_COLLECTION,
            points=[
                PointStruct(
                    id=point_id,
                    vector=vector,
                    payload=payload,
                )
            ],
        )

    def upsert_chunk_vectors(
        self,
        points: List[tuple[str, List[float], Dict[str, Any]]],
    ) -> None:
        """Batch upsert chunk vectors. Each tuple: (point_id, vector, payload)."""
        if not points:
            return
        self.client.upsert(
            collection_name=CHUNK_COLLECTION,
            points=[
                PointStruct(id=pid, vector=vec, payload=pl)
                for pid, vec, pl in points
            ],
        )

    def search_sections(
        self,
        query_vector: List[float],
        limit: int = 10,
        score_threshold: Optional[float] = None,
        filter_conditions: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Semantic search over section_embeddings with optional metadata filter."""
        q_filter = None
        if filter_conditions:
            must = []
            for key, value in filter_conditions.items():
                if isinstance(value, list):
                    must.append(
                        FieldCondition(
                            key=key,
                            match=qdrant_models.MatchAny(any=value),
                        )
                    )
                else:
                    must.append(
                        FieldCondition(key=key, match=MatchValue(value=value))
                    )
            q_filter = Filter(must=must)

        results = self.client.search(
            collection_name=SECTION_COLLECTION,
            query_vector=query_vector,
            limit=limit,
            score_threshold=score_threshold,
            query_filter=q_filter,
        )
        return [
            {"id": str(r.id), "score": r.score, "payload": r.payload or {}}
            for r in results
        ]

    def search_chunks(
        self,
        query_vector: List[float],
        limit: int = 10,
        score_threshold: Optional[float] = None,
        filter_conditions: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Semantic search over chunk_embeddings with optional metadata filter."""
        q_filter = None
        if filter_conditions:
            must = [
                FieldCondition(key=k, match=MatchValue(value=v))
                for k, v in filter_conditions.items()
            ]
            q_filter = Filter(must=must)

        results = self.client.search(
            collection_name=CHUNK_COLLECTION,
            query_vector=query_vector,
            limit=limit,
            score_threshold=score_threshold,
            query_filter=q_filter,
        )
        return [
            {"id": str(r.id), "score": r.score, "payload": r.payload or {}}
            for r in results
        ]

    def scroll_sections_by_canonical(
        self,
        canonical_section_id: str,
        edition_ids: Optional[List[str]] = None,
        tenant_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Retrieve all section points for a canonical_section_id (same section across editions)."""
        must = [
            FieldCondition(
                key="canonical_section_id",
                match=MatchValue(value=canonical_section_id),
            )
        ]
        if tenant_id:
            must.append(FieldCondition(key="tenant_id", match=MatchValue(value=tenant_id)))
        if edition_ids:
            must.append(
                FieldCondition(
                    key="edition_id",
                    match=qdrant_models.MatchAny(any=edition_ids),
                )
            )
        q_filter = Filter(must=must)
        results, _ = self.client.scroll(
            collection_name=SECTION_COLLECTION,
            scroll_filter=q_filter,
            limit=100,
            with_payload=True,
            with_vectors=False,
        )
        return [{"id": str(r.id), "payload": r.payload or {}} for r in results]


# Singleton for dependency injection
_qdrant_storage: Optional[QdrantStorage] = None


def get_qdrant_storage() -> QdrantStorage:
    global _qdrant_storage
    if _qdrant_storage is None:
        _qdrant_storage = QdrantStorage()
    return _qdrant_storage
