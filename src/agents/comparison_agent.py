"""
Comparison Agent: generate structured comparison between sections from different editions.
"""
from __future__ import annotations

from typing import Any, Dict, List

from src.agents.base_agent import BaseAgent
from src.llm.chat_client import BaseChatClient
from src.llm.prompt_templates import PromptTemplates


class ComparisonAgent(BaseAgent):
    name = "comparison"

    def __init__(
        self,
        chat_client: BaseChatClient,
        prompt_templates: PromptTemplates,
    ) -> None:
        self._chat_client = chat_client
        self._prompts = prompt_templates

    async def run(
        self,
        sections_for_comparison: List[Dict[str, Any]],
        **kwargs: Any,
    ) -> Dict[str, Any]:
        from config import get_settings
        if len(sections_for_comparison) < 2:
            return {"summary": "Need at least two sections to compare.", "dimensions": [], "citations": []}
        ed1 = sections_for_comparison[0]
        ed2 = sections_for_comparison[1]
        text1 = ed1.get("content_text", "")[:8000]
        text2 = ed2.get("content_text", "")[:8000]
        user = self._prompts.comparison(
            edition_1=ed1.get("edition_id", "") or ed1.get("edition_name", "Edition 1"),
            text_1=text1,
            edition_2=ed2.get("edition_id", "") or ed2.get("edition_name", "Edition 2"),
            text_2=text2,
        )
        try:
            out = self._chat_client.chat_with_system(
                model=get_settings().chat_model_for("compare"),
                system=self._prompts.COMPARISON_SYSTEM,
                user=user,
                temperature=0.2,
                format="json",
            )
            parsed = self._chat_client.parse_json_response(out)
        except Exception as e:
            return {"summary": f"Comparison failed: {e}", "dimensions": [], "citations": []}
        return {
            "summary": parsed.get("summary", ""),
            "dimensions": parsed.get("dimensions", []),
            "citations": parsed.get("citations", []),
            "sections_compared": parsed.get("sections_compared", []),
        }
