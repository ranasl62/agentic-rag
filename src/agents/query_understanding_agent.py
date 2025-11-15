"""
Query Understanding Agent: parse user intent and extract structured parameters.
"""
from __future__ import annotations

from typing import Any, Dict

from src.agents.base_agent import BaseAgent
from src.llm.ollama_client import OllamaClient
from src.llm.prompt_templates import PromptTemplates


class QueryUnderstandingAgent(BaseAgent):
    name = "query_understanding"

    def __init__(
        self,
        ollama_client: OllamaClient,
        prompt_templates: PromptTemplates,
    ) -> None:
        self._ollama = ollama_client
        self._prompts = prompt_templates

    async def run(
        self,
        query: str,
        available_books: str = "",
        **kwargs: Any,
    ) -> Dict[str, Any]:
        from config import get_settings
        system = self._prompts.query_understanding(available_books=available_books)
        user = f'User query: "{query}"\n\nRespond in JSON only.'
        try:
            out = self._ollama.chat_with_system(
                model=get_settings().chat_model_for("query"),
                system=system,
                user=user,
                temperature=0.1,
                format="json",
            )
            parsed = self._ollama.parse_json_response(out)
        except Exception as e:
            return {
                "intent_type": "search",
                "entities": {"books": [], "editions": [], "sections": []},
                "operations": [],
                "confidence": 0.0,
                "error": str(e),
            }
        return {
            "intent_type": parsed.get("intent_type", "search"),
            "entities": parsed.get("entities", {}),
            "operations": parsed.get("operations", []),
            "confidence": float(parsed.get("confidence", 0.5)),
            "ambiguity_note": parsed.get("ambiguity_note"),
        }
