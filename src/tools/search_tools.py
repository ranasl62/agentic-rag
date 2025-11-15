"""
Search tools: search_sections, find_same_section_across_editions, list_available_editions.
Strict input/output schemas; use vector store + metadata.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.storage.models import Book, Edition, Section
from src.storage.qdrant_client import QdrantStorage
from src.tools.base_tool import BaseTool, ToolResult, ToolInput


class SearchSectionsInput(ToolInput):
    query: str = Field(..., description="Natural language or keyword search query")
    limit: int = Field(default=10, ge=1, le=50)
    book_id: Optional[str] = None
    edition_id: Optional[str] = None
    score_threshold: Optional[float] = Field(default=None, ge=0, le=1)


class FindSameSectionInput(ToolInput):
    book_id: str = Field(..., description="UUID of the book")
    canonical_section_id: Optional[str] = Field(None, description="Stable section id e.g. book_001_ch03_sec02")
    chapter_number: Optional[int] = None
    section_number: Optional[int] = None
    edition_ids: Optional[List[str]] = Field(default=None, description="Filter to these edition UUIDs")


class ListEditionsInput(ToolInput):
    book_id: Optional[str] = Field(None, description="If set, list only editions of this book")


class SearchSectionsTool(BaseTool):
    name = "search_sections"
    description = "Semantic search across sections. Optional filters: book_id, edition_id."
    input_schema = SearchSectionsInput

    def __init__(
        self,
        qdrant: QdrantStorage,
        embedding_service: Any,
        session_factory: Any,
    ) -> None:
        self._qdrant = qdrant
        self._embedding_service = embedding_service
        self._session_factory = session_factory

    async def execute(
        self,
        query: str,
        limit: int = 10,
        book_id: Optional[str] = None,
        edition_id: Optional[str] = None,
        score_threshold: Optional[float] = None,
        tenant_id: Optional[str] = None,
        **kwargs: Any,
    ) -> ToolResult:
        try:
            vector = self._embedding_service.embed(query)
        except Exception as e:
            return ToolResult(success=False, error=f"Embedding failed: {e}")
        filter_conditions: Dict[str, Any] = {}
        if tenant_id:
            filter_conditions["tenant_id"] = tenant_id
        if book_id:
            filter_conditions["book_id"] = book_id
        if edition_id:
            filter_conditions["edition_id"] = edition_id
        results = self._qdrant.search_sections(
            query_vector=vector,
            limit=limit,
            score_threshold=score_threshold,
            filter_conditions=filter_conditions or None,
        )
        citations = []
        for r in results:
            p = r.get("payload") or {}
            citations.append({
                "section_id": p.get("section_id"),
                "edition_id": p.get("edition_id"),
                "book_id": p.get("book_id"),
                "location_path": p.get("location_path"),
                "content_preview": p.get("content_preview", "")[:200],
                "score": r.get("score"),
            })
        return ToolResult(
            success=True,
            data={"results": citations, "count": len(citations)},
            citations=citations,
        )


class FindSameSectionAcrossEditionsTool(BaseTool):
    name = "find_same_section_across_editions"
    description = "Find the same logical section across editions by canonical_section_id or chapter/section numbers."
    input_schema = FindSameSectionInput

    def __init__(
        self,
        qdrant: QdrantStorage,
        session_factory: Any,
    ) -> None:
        self._qdrant = qdrant
        self._session_factory = session_factory

    async def execute(
        self,
        book_id: str,
        canonical_section_id: Optional[str] = None,
        chapter_number: Optional[int] = None,
        section_number: Optional[int] = None,
        edition_ids: Optional[List[str]] = None,
        tenant_id: Optional[str] = None,
        **kwargs: Any,
    ) -> ToolResult:
        async with self._session_factory() as session:
            if canonical_section_id:
                # Resolve from Qdrant by canonical id
                points = self._qdrant.scroll_sections_by_canonical(
                    canonical_section_id=canonical_section_id,
                    edition_ids=edition_ids,
                    tenant_id=tenant_id,
                )
                if not points:
                    return ToolResult(
                        success=True,
                        data={"sections": [], "canonical_section_id": canonical_section_id},
                        citations=[],
                    )
                section_ids = []
                for p in points:
                    if not p.get("payload"):
                        continue
                    sid = p["payload"].get("section_id")
                    if sid is None:
                        continue
                    section_ids.append(UUID(sid) if isinstance(sid, str) else sid)
                if not section_ids:
                    return ToolResult(success=True, data={"sections": [], "canonical_section_id": canonical_section_id}, citations=[])
                # Load full sections from DB (tenant-scoped when tenant_id provided)
                if tenant_id:
                    stmt = (
                        select(Section)
                        .join(Edition)
                        .join(Book)
                        .where(Book.tenant_id == UUID(tenant_id))
                        .where(Section.section_id.in_(section_ids))
                    )
                else:
                    stmt = select(Section).where(Section.section_id.in_(section_ids))
                result = await session.execute(stmt)
                sections = list(result.scalars().all())
            else:
                # Find canonical_section_id by book + chapter + section (tenant-scoped via Book)
                stmt = (
                    select(Section)
                    .join(Edition)
                    .join(Book)
                    .where(Edition.book_id == UUID(book_id))
                    .where(Section.chapter_number == chapter_number)
                    .where(Section.section_number == section_number)
                )
                if tenant_id:
                    stmt = stmt.where(Book.tenant_id == UUID(tenant_id))
                if edition_ids:
                    stmt = stmt.where(Edition.edition_id.in_([UUID(e) for e in edition_ids]))
                res = await session.execute(stmt)
                sections = list(res.scalars().all())
                if not sections:
                    return ToolResult(
                        success=True,
                        data={"sections": [], "message": "No sections found for given book/chapter/section"},
                        citations=[],
                    )
                canonical_section_id = sections[0].canonical_section_id
                # Optionally fetch all editions for this canonical id (tenant-scoped)
                stmt2 = select(Section).join(Edition).join(Book).where(Section.canonical_section_id == canonical_section_id)
                if tenant_id:
                    stmt2 = stmt2.where(Book.tenant_id == UUID(tenant_id))
                res2 = await session.execute(stmt2)
                sections = list(res2.scalars().all())

            section_data = []
            for s in sections:
                section_data.append({
                    "section_id": str(s.section_id),
                    "edition_id": str(s.edition_id),
                    "canonical_section_id": s.canonical_section_id,
                    "location_path": s.location_path,
                    "content_text": s.content_text,
                    "chapter_number": s.chapter_number,
                    "section_number": s.section_number,
                })
            citations = [
                {"section_id": d["section_id"], "edition_id": d["edition_id"], "location_path": d["location_path"]}
                for d in section_data
            ]
            return ToolResult(
                success=True,
                data={"sections": section_data, "canonical_section_id": canonical_section_id or sections[0].canonical_section_id},
                citations=citations,
            )


class ListAvailableEditionsTool(BaseTool):
    name = "list_available_editions"
    description = "List books and their editions. Optionally filter by book_id."
    input_schema = ListEditionsInput

    def __init__(self, session_factory: Any) -> None:
        self._session_factory = session_factory

    async def execute(
        self,
        book_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        **kwargs: Any,
    ) -> ToolResult:
        async with self._session_factory() as session:
            stmt = select(Book, Edition).join(Edition, Edition.book_id == Book.book_id)
            if tenant_id:
                stmt = stmt.where(Book.tenant_id == UUID(tenant_id))
            if book_id:
                stmt = stmt.where(Book.book_id == UUID(book_id))
            result = await session.execute(stmt)
            rows = result.all()
            books: Dict[str, Any] = {}
            for book, edition in rows:
                bid = str(book.book_id)
                if bid not in books:
                    books[bid] = {"book_id": bid, "title": book.title, "author": book.author, "editions": []}
                books[bid]["editions"].append({
                    "edition_id": str(edition.edition_id),
                    "edition_name": edition.edition_name,
                    "publication_year": edition.publication_year,
                })
            return ToolResult(
                success=True,
                data={"books": list(books.values())},
                citations=[],
            )


def search_sections_tool(
    qdrant: QdrantStorage,
    embedding_service: Any,
    session_factory: Any,
) -> SearchSectionsTool:
    return SearchSectionsTool(qdrant, embedding_service, session_factory)


def find_same_section_across_editions_tool(
    qdrant: QdrantStorage,
    session_factory: Any,
) -> FindSameSectionAcrossEditionsTool:
    return FindSameSectionAcrossEditionsTool(qdrant, session_factory)


def list_available_editions_tool(session_factory: Any) -> ListAvailableEditionsTool:
    return ListAvailableEditionsTool(session_factory)
