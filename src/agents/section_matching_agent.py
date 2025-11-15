"""
Section Matching Agent: decide if two sections from different editions are the same.
Used when no precomputed alignment exists; scores candidates.
"""
from __future__ import annotations

from typing import Any, Dict

from src.agents.base_agent import BaseAgent
from src.llm.ollama_client import OllamaClient
from src.llm.prompt_templates import PromptTemplates


class SectionMatchingAgent(BaseAgent):
    name = "section_matching"

    def __init__(
        self,
        ollama_client: OllamaClient,
        prompt_templates: PromptTemplates,
    ) -> None:
        self._ollama = ollama_client
        self._prompts = prompt_templates

    async def run(
        self,
        location_a: str,
        title_a: str,
        preview_a: str,
        location_b: str,
        title_b: str,
        preview_b: str,
        structural_sim: float = 0.0,
        semantic_sim: float = 0.0,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        from config import get_settings
        user = self._prompts.section_matching(
            location_a=location_a,
            title_a=title_a,
            preview_a=preview_a,
            location_b=location_b,
            title_b=title_b,
            preview_b=preview_b,
            structural_sim=structural_sim,
            semantic_sim=semantic_sim,
        )
        try:
            out = self._ollama.chat_with_system(
                model=get_settings().chat_model_for("query"),
                system=self._prompts.SECTION_MATCHING_SYSTEM,
                user=user,
                temperature=0.1,
                format="json",
            )
            parsed = self._ollama.parse_json_response(out)
        except Exception as e:
            return {"same_section": False, "confidence": 0.0, "reasoning": str(e)}
        return {
            "same_section": bool(parsed.get("same_section", False)),
            "confidence": float(parsed.get("confidence", 0.0)),
            "reasoning": parsed.get("reasoning", ""),
        }
