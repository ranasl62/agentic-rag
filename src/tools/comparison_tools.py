"""
Comparison tool: returns structured content for two or more sections so the Comparison Agent can summarize.
"""
from __future__ import annotations

from typing import Any, List

from pydantic import Field

from src.tools.base_tool import BaseTool, ToolResult, ToolInput


class CompareSectionsInput(ToolInput):
    section_payloads: List[dict] = Field(
        ...,
        description="List of section objects with edition_id, location_path, content_text",
        min_length=2,
    )


class CompareSectionsTool(BaseTool):
    """
    Accepts a list of section payloads (from find_same_section_across_editions or search).
    Returns them in a deterministic order for the Comparison Agent.
    Does not call LLM; purely structural.
    """
    name = "compare_sections"
    description = "Prepare section payloads for comparison. Input: list of {edition_id, location_path, content_text}."
    input_schema = CompareSectionsInput

    async def execute(
        self,
        section_payloads: List[dict],
        **kwargs: Any,
    ) -> ToolResult:
        normalized = []
        for i, p in enumerate(section_payloads):
            normalized.append({
                "index": i + 1,
                "edition_id": p.get("edition_id"),
                "location_path": p.get("location_path", ""),
                "content_text": p.get("content_text", ""),
                "content_length": len(p.get("content_text") or ""),
            })
        citations = [
            {"edition_id": p.get("edition_id"), "location_path": p.get("location_path")}
            for p in normalized
        ]
        return ToolResult(
            success=True,
            data={"sections_for_comparison": normalized, "count": len(normalized)},
            citations=citations,
        )


def compare_sections_tool() -> CompareSectionsTool:
    return CompareSectionsTool()
