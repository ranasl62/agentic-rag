"""
Summarization Agent: single section summary or multi-section/evolution summary.
"""
from __future__ import annotations

from typing import Any, Dict

from src.agents.base_agent import BaseAgent
from src.llm.chat_client import BaseChatClient
from src.llm.prompt_templates import PromptTemplates


class SummarizationAgent(BaseAgent):
    name = "summarization"

    def __init__(
        self,
        chat_client: BaseChatClient,
        prompt_templates: PromptTemplates,
    ) -> None:
        self._chat_client = chat_client
        self._prompts = prompt_templates

    async def run(
        self,
        summary_type: str,
        content: str,
        max_length: int = 300,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        from config import get_settings
        user = self._prompts.summarization(
            summary_type=summary_type,
            content=content,
            max_length=max_length,
        )
        try:
            out = self._chat_client.chat_with_system(
                model=get_settings().chat_model_for("summarize"),
                system=self._prompts.SUMMARIZATION_SYSTEM,
                user=user,
                temperature=0.2,
                format="json",
            )
            parsed = self._chat_client.parse_json_response(out)
        except Exception as e:
            return {"content": "", "citations": [], "confidence": 0.0, "error": str(e)}
        return {
            "content": parsed.get("content", parsed.get("summary", "")),
            "citations": parsed.get("citations", []),
            "confidence": float(parsed.get("confidence", 0.8)),
            "summary_type": summary_type,
        }
