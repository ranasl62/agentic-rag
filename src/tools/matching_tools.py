"""
Section matching tool: align sections across editions (structural + semantic).
"""
from __future__ import annotations

from typing import Any, List, Optional

from pydantic import Field

from src.tools.base_tool import BaseTool, ToolResult, ToolInput


class MatchSectionsInput(ToolInput):
    source_section_id: str = Field(..., description="Section UUID from one edition")
    target_edition_id: str = Field(..., description="Edition UUID to find matching section in")
    candidate_section_ids: Optional[List[str]] = Field(
        None,
        description="If provided, only consider these section UUIDs as candidates",
    )


class MatchSectionsTool(BaseTool):
    """
    Match one section to the same logical section in another edition.
    Uses precomputed section_alignments when available; otherwise returns candidates
    for the Section Matching Agent to score.
    """
    name = "match_sections"
    description = "Find the section in target_edition that corresponds to source_section (same logical section)."
    input_schema = MatchSectionsInput

    def __init__(self, session_factory: Any) -> None:
        self._session_factory = session_factory

    async def execute(
        self,
        source_section_id: str,
        target_edition_id: str,
        candidate_section_ids: Optional[List[str]] = None,
        tenant_id: Optional[str] = None,
        **kwargs: Any,
    ) -> ToolResult:
        from uuid import UUID
        from sqlalchemy import select
        from src.storage.models import Section, SectionAlignment, Edition, Book

        async with self._session_factory() as session:
            # Check alignments first (target sections scoped by edition; tenant filter below if needed)
            subq = select(Section.section_id).where(Section.edition_id == UUID(target_edition_id))
            stmt = select(SectionAlignment).where(
                SectionAlignment.source_section_id == UUID(source_section_id),
                SectionAlignment.target_section_id.in_(subq),
            )
            result = await session.execute(stmt)
            alignment = result.scalars().first()
            if alignment:
                # If tenant_id required, ensure target edition belongs to tenant
                if tenant_id:
                    check = select(Book).join(Edition).where(
                        Edition.edition_id == UUID(target_edition_id),
                        Book.tenant_id == UUID(tenant_id),
                    )
                    r = await session.execute(check)
                    if r.scalars().first() is None:
                        alignment = None  # treat as no alignment (tenant mismatch)
                if alignment:
                    return ToolResult(
                        success=True,
                        data={
                            "matched_section_id": str(alignment.target_section_id),
                            "alignment_score": alignment.alignment_score,
                            "alignment_method": alignment.alignment_method,
                        },
                        citations=[{"section_id": str(alignment.target_section_id), "edition_id": target_edition_id}],
                    )
            # No precomputed alignment: return candidates for agent to rank (tenant-scoped)
            stmt = select(Section).join(Edition).join(Book).where(Section.edition_id == UUID(target_edition_id))
            if tenant_id:
                stmt = stmt.where(Book.tenant_id == UUID(tenant_id))
            if candidate_section_ids:
                stmt = stmt.where(Section.section_id.in_([UUID(c) for c in candidate_section_ids]))
            stmt = stmt.order_by(Section.sequence_number).limit(20)
            res = await session.execute(stmt)
            candidates = res.scalars().all()
            return ToolResult(
                success=True,
                data={
                    "candidates": [
                        {
                            "section_id": str(c.section_id),
                            "location_path": c.location_path,
                            "section_title": c.section_title,
                            "content_preview": c.content_text[:300],
                        }
                        for c in candidates
                    ],
                    "message": "No alignment found; use section_matching_agent to score candidates",
                },
                citations=[],
            )


def match_sections_tool(session_factory: Any) -> MatchSectionsTool:
    return MatchSectionsTool(session_factory)
