"""
Verification / Grounding Agent: ensure response is grounded in retrieved context.
"""
from __future__ import annotations

from typing import Any, Dict

from src.agents.base_agent import BaseAgent
from src.llm.ollama_client import OllamaClient
from src.llm.prompt_templates import PromptTemplates


class VerificationAgent(BaseAgent):
    name = "verification"

    def __init__(
        self,
        ollama_client: OllamaClient,
        prompt_templates: PromptTemplates,
    ) -> None:
        self._ollama = ollama_client
        self._prompts = prompt_templates

    async def run(
        self,
        response: str,
        source_context: str,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        from config import get_settings
        user = self._prompts.verification(response=response, source_context=source_context)
        try:
            out = self._ollama.chat_with_system(
                model=get_settings().chat_model_for("verify"),
                system=self._prompts.VERIFICATION_SYSTEM,
                user=user,
                temperature=0.1,
                format="json",
            )
            parsed = self._ollama.parse_json_response(out)
        except Exception as e:
            return {"is_grounded": False, "unsupported_claims": [str(e)], "citation_errors": []}
        return {
            "is_grounded": bool(parsed.get("is_grounded", False)),
            "unsupported_claims": parsed.get("unsupported_claims", []),
            "citation_errors": parsed.get("citation_errors", []),
        }
