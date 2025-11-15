"""Books and sections listing."""
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from typing import Optional
from src.api.auth import TenantInfo, get_current_tenant
from src.api.rate_limit import rate_limit_dependency
from src.api.schemas import BooksResponse, BookInfo, SectionInfo
from src.storage.postgres_client import get_async_session
from src.storage.models import Book, Edition, Section

router = APIRouter(prefix="/books", tags=["books"])


@router.get("", response_model=BooksResponse)
async def list_books(
    session: AsyncSession = Depends(get_async_session),
    tenant: TenantInfo = Depends(get_current_tenant),
    _=Depends(rate_limit_dependency("list")),
):
    stmt = select(Book).where(Book.tenant_id == tenant.tenant_id).order_by(Book.title)
    result = await session.execute(stmt)
    books = list(result.scalars().all())
    out = []
    for b in books:
        stmt = select(Edition).where(Edition.book_id == b.book_id)
        res = await session.execute(stmt)
        editions = list(res.scalars().all())
        out.append(
            BookInfo(
                book_id=str(b.book_id),
                title=b.title,
                author=b.author,
                editions=[
                    {"edition_id": str(e.edition_id), "edition_name": e.edition_name, "publication_year": e.publication_year}
                    for e in editions
                ],
            )
        )
    return BooksResponse(books=out)


@router.get("/sections")
async def list_sections(
    book_id: Optional[str] = None,
    edition_id: Optional[str] = None,
    session: AsyncSession = Depends(get_async_session),
    tenant: TenantInfo = Depends(get_current_tenant),
    _=Depends(rate_limit_dependency("list")),
):
    stmt = select(Section).join(Edition).join(Book).where(Book.tenant_id == tenant.tenant_id)
    if edition_id:
        stmt = stmt.where(Section.edition_id == UUID(edition_id))
    elif book_id:
        stmt = stmt.where(Edition.book_id == UUID(book_id))
    stmt = stmt.order_by(Section.sequence_number)
    result = await session.execute(stmt)
    sections = list(result.scalars().all())
    return {
        "sections": [
            SectionInfo(
                section_id=str(s.section_id),
                edition_id=str(s.edition_id),
                canonical_section_id=s.canonical_section_id,
                location_path=s.location_path,
                content_length=s.content_length,
            )
            for s in sections
        ]
    }
