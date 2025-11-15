"""Search endpoint: semantic search across sections. Optional LLM answer."""
from fastapi import APIRouter, Depends, HTTPException

from config import get_settings
from src.api.auth import TenantInfo, get_current_tenant
from src.api.cache import get_search_cached, set_search_cached
from src.api.rate_limit import rate_limit_dependency
from src.api.schemas import SearchRequest, SearchResponse, SearchResultItem, Citation
from src.storage.qdrant_client import get_qdrant_storage
from src.llm.embeddings import get_embedding_service

router = APIRouter(prefix="/search", tags=["search"])


@router.post("", response_model=SearchResponse)
async def search(
    body: SearchRequest,
    tenant: TenantInfo = Depends(get_current_tenant),
    _=Depends(rate_limit_dependency("search")),
):
    if not body.skip_cache:
        cached = await get_search_cached(
            tenant.tenant_id, body.query, body.book_id, body.edition_id, body.limit, body.generate_answer
        )
        if cached is not None:
            return SearchResponse.model_validate(cached)

    try:
        qdrant = get_qdrant_storage()
        embedding = get_embedding_service()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Search unavailable: {e!s}")

    try:
        vector = embedding.embed(body.query)
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"Embedding failed. Is Ollama running with nomic-embed-text? {e!s}",
        )

    filter_conditions = {"tenant_id": str(tenant.tenant_id)}
    if body.book_id:
        filter_conditions["book_id"] = body.book_id
    if body.edition_id:
        filter_conditions["edition_id"] = body.edition_id

    try:
        results = qdrant.search_sections(
            query_vector=vector,
            limit=body.limit,
            filter_conditions=filter_conditions or None,
        )
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Vector search failed: {e!s}")

    items = []
    citations = []
    for r in results:
        p = r.get("payload") or {}
        items.append(
            SearchResultItem(
                section_id=p.get("section_id"),
                edition_id=p.get("edition_id"),
                book_id=p.get("book_id"),
                location_path=p.get("location_path"),
                content_preview=p.get("content_preview"),
                score=r.get("score"),
            )
        )
        citations.append(
            Citation(
                section_id=p.get("section_id"),
                edition_id=p.get("edition_id"),
                book_id=p.get("book_id"),
                location_path=p.get("location_path"),
            )
        )

    answer: str | None = None
    if body.generate_answer and items:
        try:
            from src.llm.chat_client import get_chat_client
            ollama = get_chat_client()
            context_parts = []
            for i, it in enumerate(items[:10], 1):
                loc = it.location_path or "Section"
                prev = (it.content_preview or "").strip()
                if prev:
                    context_parts.append(f"[{loc}]\n{prev}")
            context = "\n\n".join(context_parts)[:6000]
            system = (
                "You are a helpful assistant. Answer the user's question based ONLY on the following excerpts from a book. "
                "Answer exactly what was asked: do not assume they are asking about an 'interview' or a specific topic unless the question clearly says so. "
                "Be concise (2-4 sentences). If the excerpts do not contain enough information, say so. Do not make up facts."
            )
            user = f"Excerpts:\n{context}\n\nQuestion: {body.query}\n\nAnswer:"
            answer = ollama.chat(
                model=get_settings().chat_model_for("search_answer"),
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                temperature=0.2,
                format=None,
            )
        except Exception as e:
            answer = f"(Could not generate answer: {e!s})"

    response = SearchResponse(success=True, results=items, citations=citations, answer=answer)
    if not body.skip_cache:
        await set_search_cached(
            tenant.tenant_id, body.query, body.book_id, body.edition_id, body.limit,
            response.model_dump(),
            body.generate_answer,
        )
    return response
