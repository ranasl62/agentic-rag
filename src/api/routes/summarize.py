"""Summarize endpoint: single section or differences."""
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.auth import TenantInfo, get_current_tenant
from src.api.rate_limit import rate_limit_dependency
from src.api.schemas import SummarizeRequest, SummarizeResponse, Citation
from src.api.dependencies import get_orchestrator
from src.storage.postgres_client import get_async_session
from src.storage.models import Section, Edition, Book

router = APIRouter(prefix="/summarize", tags=["summarize"])


async def _sections_for_tenant(session, tenant_id, section_uuids):
    stmt = (
        select(Section)
        .join(Edition)
        .join(Book)
        .where(Book.tenant_id == tenant_id)
        .where(Section.section_id.in_(section_uuids))
    )
    result = await session.execute(stmt)
    return result.scalars().all()


@router.post("", response_model=SummarizeResponse)
async def summarize(
    body: SummarizeRequest,
    session: AsyncSession = Depends(get_async_session),
    tenant: TenantInfo = Depends(get_current_tenant),
    _=Depends(rate_limit_dependency("summarize")),
):
    if body.section_ids and len(body.section_ids) >= 2:
        sections = await _sections_for_tenant(
            session, tenant.tenant_id, [UUID(s) for s in body.section_ids]
        )
        sections = list(sections)
        if len(sections) < 2:
            return SummarizeResponse(success=False, summary="Need at least two sections to summarize differences.")
        from src.llm.chat_client import get_chat_client
        from src.llm.prompt_templates import PromptTemplates
        from config import get_settings
        ollama = get_chat_client()
        prompts = PromptTemplates()
        content = "\n\n---\n\n".join(
            f"Edition: {s.edition_id}\n{s.location_path}\n\n{s.content_text[:4000]}"
            for s in sections
        )
        user = prompts.summarization(summary_type="differences", content=content, max_length=body.max_length)
        out = ollama.chat_with_system(
            model=get_settings().chat_model_for("summarize"),
            system=prompts.SUMMARIZATION_SYSTEM,
            user=user,
            temperature=0.2,
            format=None,
        )
        citations = [Citation(section_id=str(s.section_id), edition_id=str(s.edition_id), location_path=s.location_path) for s in sections]
        return SummarizeResponse(success=True, summary=out, citations=citations)
    if body.section_ids and len(body.section_ids) == 1:
        section_list = await _sections_for_tenant(
            session, tenant.tenant_id, [UUID(body.section_ids[0])]
        )
        section = section_list[0] if section_list else None
        if not section:
            return SummarizeResponse(success=False, summary="Section not found.")
        from src.llm.chat_client import get_chat_client
        from src.llm.prompt_templates import PromptTemplates
        from config import get_settings
        ollama = get_chat_client()
        prompts = PromptTemplates()
        user = prompts.summarization(
            summary_type="section",
            content=f"{section.location_path}\n\n{section.content_text}",
            max_length=body.max_length,
        )
        out = ollama.chat_with_system(
            model=get_settings().chat_model_for("summarize"),
            system=prompts.SUMMARIZATION_SYSTEM,
            user=user,
            temperature=0.2,
            format=None,
        )
        return SummarizeResponse(
            success=True,
            summary=out,
            citations=[Citation(section_id=str(section.section_id), edition_id=str(section.edition_id), location_path=section.location_path)],
        )
    if body.query:
        orch = get_orchestrator()
        out = await orch.run(
            query=body.query,
            skip_verification=True,
            tenant_id=tenant.tenant_id,
        )
        raw_cites = out.get("citations", [])
        citations = [
            Citation(
                section_id=c.get("section_id") if isinstance(c, dict) else None,
                edition_id=c.get("edition_id") if isinstance(c, dict) else None,
                location_path=c.get("location_path") if isinstance(c, dict) else None,
            )
            for c in raw_cites
        ]
        return SummarizeResponse(
            success=True,
            summary=out.get("response", ""),
            citations=citations,
        )
    return SummarizeResponse(success=False, summary="Provide section_ids or query.")
