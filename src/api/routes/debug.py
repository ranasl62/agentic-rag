"""Debug/diagnostic endpoints for troubleshooting search and vectors. Require auth (Phase 1)."""
from fastapi import APIRouter, Depends, HTTPException

from src.api.auth import TenantInfo, get_current_tenant
from src.storage.qdrant_client import get_qdrant_storage, SECTION_COLLECTION, CHUNK_COLLECTION
from src.llm.embeddings import get_embedding_service

router = APIRouter(prefix="/debug", tags=["debug"])


@router.get("/vector-status")
async def vector_status(_: TenantInfo = Depends(get_current_tenant)):
    """
    Check if vector store has data and search works.
    Returns collection point counts and a sample search result count.
    """
    try:
        qdrant = get_qdrant_storage()
        embedding = get_embedding_service()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Failed to get storage or embedding: {e}")

    out = {"section_collection": SECTION_COLLECTION, "chunk_collection": CHUNK_COLLECTION}

    try:
        for name in (SECTION_COLLECTION, CHUNK_COLLECTION):
            try:
                info = qdrant.client.get_collection(name)
                out[name] = {
                    "points_count": getattr(info, "points_count", None),
                    "vectors_count": getattr(info, "vectors_count", None),
                }
            except Exception as e:
                out[name] = {"error": str(e)}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Qdrant error: {e}")

    # Scroll first few points to confirm data is present
    try:
        scroll_result, _ = qdrant.client.scroll(
            collection_name=SECTION_COLLECTION,
            limit=3,
            with_payload=True,
            with_vectors=False,
        )
        out["scroll_sample"] = {"count": len(scroll_result)}
        if scroll_result:
            p = getattr(scroll_result[0], "payload", None) or {}
            out["scroll_sample"]["first_payload_keys"] = list(p.keys())
    except Exception as e:
        out["scroll_sample"] = {"error": str(e)}

    # Run one search to verify end-to-end
    try:
        vector = embedding.embed("system design")
        results = qdrant.search_sections(query_vector=vector, limit=5)
        out["sample_search"] = {"query": "system design", "results_count": len(results)}
        if results:
            out["sample_search"]["first_score"] = results[0].get("score")
            out["sample_search"]["first_preview"] = (results[0].get("payload") or {}).get("content_preview", "")[:100]
    except Exception as e:
        out["sample_search"] = {"error": str(e)}

    return out
