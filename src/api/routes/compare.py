"""Compare endpoint: same section across editions."""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.auth import TenantInfo, get_current_tenant
from src.api.rate_limit import rate_limit_dependency
from src.api.schemas import CompareRequest, CompareResponse, Citation
from src.storage.postgres_client import get_async_session
from src.storage.models import Section, Edition, Book
from src.storage.qdrant_client import get_qdrant_storage

router = APIRouter(prefix="/compare", tags=["compare"])


@router.post("", response_model=CompareResponse)
async def compare(
    body: CompareRequest,
    session: AsyncSession = Depends(get_async_session),
    tenant: TenantInfo = Depends(get_current_tenant),
    _=Depends(rate_limit_dependency("compare")),
):
    doc_id = body.get_document_id()
    if not body.canonical_section_id and not doc_id:
        raise HTTPException(status_code=400, detail="Either document_id (or book_id) or canonical_section_id is required")
    if body.canonical_section_id:
        qdrant = get_qdrant_storage()
        points = qdrant.scroll_sections_by_canonical(
            canonical_section_id=body.canonical_section_id,
            edition_ids=body.edition_ids,
            tenant_id=str(tenant.tenant_id),
        )
        section_ids = []
        for p in points:
            if not p.get("payload"):
                continue
            sid = p["payload"].get("section_id")
            if sid:
                section_ids.append(UUID(sid) if isinstance(sid, str) else sid)
        if not section_ids:
            return CompareResponse(success=True, sections=[], canonical_section_id=body.canonical_section_id)
        stmt = (
            select(Section)
            .join(Edition)
            .join(Book)
            .where(Book.tenant_id == tenant.tenant_id)
            .where(Section.section_id.in_(section_ids))
        )
        result = await session.execute(stmt)
        sections = list(result.scalars().all())
    else:
        stmt = (
            select(Section)
            .join(Edition)
            .join(Book)
            .where(Book.tenant_id == tenant.tenant_id)
            .where(Edition.book_id == UUID(doc_id))
            .where(Section.chapter_number == body.chapter_number)
            .where(Section.section_number == body.section_number)
        )
        if body.edition_ids:
            stmt = stmt.where(Edition.edition_id.in_([UUID(e) for e in body.edition_ids]))
        res = await session.execute(stmt)
        sections = list(res.scalars().all())
        if not sections:
            return CompareResponse(success=True, sections=[], citations=[])
        canonical = sections[0].canonical_section_id
        stmt2 = (
            select(Section)
            .join(Edition)
            .join(Book)
            .where(Book.tenant_id == tenant.tenant_id)
            .where(Section.canonical_section_id == canonical)
        )
        res2 = await session.execute(stmt2)
        sections = list(res2.scalars().all())

    section_data = [
        {
            "section_id": str(s.section_id),
            "edition_id": str(s.edition_id),
            "canonical_section_id": s.canonical_section_id,
            "location_path": s.location_path,
            "content_text": s.content_text,
        }
        for s in sections
    ]
    citations = [
        Citation(section_id=s["section_id"], edition_id=s["edition_id"], location_path=s["location_path"])
        for s in section_data
    ]
    return CompareResponse(
        success=True,
        sections=section_data,
        canonical_section_id=sections[0].canonical_section_id if sections else None,
        citations=citations,
    )
