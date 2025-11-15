"""
Retrieval Planning Agent: determine optimal retrieval strategy from query intent.
"""
from __future__ import annotations

from typing import Any, Dict

from src.agents.base_agent import BaseAgent
from src.llm.ollama_client import OllamaClient
from src.llm.prompt_templates import PromptTemplates


class RetrievalPlanningAgent(BaseAgent):
    name = "retrieval_planning"

    def __init__(
        self,
        ollama_client: OllamaClient,
        prompt_templates: PromptTemplates,
    ) -> None:
        self._ollama = ollama_client
        self._prompts = prompt_templates

    async def run(
        self,
        query_intent: Dict[str, Any],
        **kwargs: Any,
    ) -> Dict[str, Any]:
        from config import get_settings
        import json
        system = self._prompts.retrieval_planning()
        user = f"Query intent:\n{json.dumps(query_intent, indent=2)}\n\nRespond in JSON only."
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
                "strategy": "section_semantic",
                "steps": [{"tool": "search_sections", "parameters": {"query": kwargs.get("query", "")}, "reasoning": "fallback"}],
                "expected_sections": 10,
                "error": str(e),
            }
        return {
            "strategy": parsed.get("strategy", "section_semantic"),
            "steps": parsed.get("steps", []),
            "expected_sections": parsed.get("expected_sections", 10),
            "fallback_strategy": parsed.get("fallback_strategy"),
        }
