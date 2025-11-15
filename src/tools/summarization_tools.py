"""
Summarization tools: summarize_section, summarize_differences.
Delegate to LLM with strict prompts; return summary + citations.
"""
from __future__ import annotations

from typing import Any, List, Optional

from pydantic import Field

from src.tools.base_tool import BaseTool, ToolResult, ToolInput


class SummarizeSectionInput(ToolInput):
    content_text: str = Field(..., description="Full section text to summarize")
    location_path: str = Field(default="", description="Section location for citation")
    edition_id: Optional[str] = None
    max_length: int = Field(default=300, ge=50, le=1000)


class SummarizeDifferencesInput(ToolInput):
    section_summaries: List[dict] = Field(
        ...,
        description="List of {edition_id, edition_name, content_text or summary, location_path}",
        min_length=2,
    )
    max_length: int = Field(default=500, ge=100, le=2000)


class SummarizeSectionTool(BaseTool):
    name = "summarize_section"
    description = "Summarize a single section concisely with citation."
    input_schema = SummarizeSectionInput

    def __init__(self, ollama_client: Any, prompt_templates: Any) -> None:
        self._ollama = ollama_client
        self._prompts = prompt_templates

    async def execute(
        self,
        content_text: str,
        location_path: str = "",
        edition_id: Optional[str] = None,
        max_length: int = 300,
        **kwargs: Any,
    ) -> ToolResult:
        from config import get_settings
        prompt = self._prompts.summarization(
            summary_type="section",
            content=f"Location: {location_path}\n\n{content_text}",
            max_length=max_length,
        )
        try:
            out = self._ollama.chat_with_system(
                model=get_settings().chat_model_for("summarize"),
                system=self._prompts.SUMMARIZATION_SYSTEM,
                user=prompt,
                temperature=0.2,
                format=None,
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e))
        citations = [{"edition_id": edition_id, "location_path": location_path}]
        return ToolResult(
            success=True,
            data={"summary": out, "location_path": location_path, "edition_id": edition_id},
            citations=citations,
        )


class SummarizeDifferencesTool(BaseTool):
    name = "summarize_differences"
    description = "Summarize differences between the same section across editions."
    input_schema = SummarizeDifferencesInput

    def __init__(self, ollama_client: Any, prompt_templates: Any) -> None:
        self._ollama = ollama_client
        self._prompts = prompt_templates

    async def execute(
        self,
        section_summaries: List[dict],
        max_length: int = 500,
        **kwargs: Any,
    ) -> ToolResult:
        from config import get_settings
        parts = []
        for s in section_summaries:
            parts.append(
                f"Edition: {s.get('edition_name') or s.get('edition_id')}\n"
                f"Location: {s.get('location_path', '')}\n\n"
                f"{s.get('content_text') or s.get('summary', '')}"
            )
        content = "\n\n---\n\n".join(parts)
        prompt = self._prompts.summarization(
            summary_type="differences",
            content=content,
            max_length=max_length,
        )
        try:
            out = self._ollama.chat_with_system(
                model=get_settings().chat_model_for("summarize"),
                system=self._prompts.SUMMARIZATION_SYSTEM,
                user=prompt,
                temperature=0.2,
                format=None,
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e))
        citations = [
            {"edition_id": s.get("edition_id"), "location_path": s.get("location_path")}
            for s in section_summaries
        ]
        return ToolResult(
            success=True,
            data={"summary": out, "editions_compared": len(section_summaries)},
            citations=citations,
        )


def summarize_section_tool(ollama_client: Any, prompt_templates: Any) -> SummarizeSectionTool:
    return SummarizeSectionTool(ollama_client, prompt_templates)


def summarize_differences_tool(ollama_client: Any, prompt_templates: Any) -> SummarizeDifferencesTool:
    return SummarizeDifferencesTool(ollama_client, prompt_templates)
