"""
Ollama HTTP client for chat completion. Embeddings are in a separate module.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from config import get_settings


class OllamaClient:
    """Sync HTTP client for Ollama API (chat). Used by agents."""

    def __init__(self, base_url: Optional[str] = None) -> None:
        s = get_settings()
        self._base_url = (base_url or s.ollama_base_url).rstrip("/")

    def _url(self, path: str) -> str:
        return f"{self._base_url}{path}"

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True,
    )
    def chat(
        self,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.2,
        format: Optional[str] = "json",
    ) -> str:
        """
        Send chat completion request. Returns the content of the assistant message.
        If format is 'json', response is expected to be valid JSON (for agent outputs).
        """
        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": temperature},
        }
        if format:
            payload["format"] = format
        with httpx.Client(timeout=120.0) as client:
            resp = client.post(self._url("/api/chat"), json=payload)
            resp.raise_for_status()
        data = resp.json()
        content = (data.get("message") or {}).get("content") or ""
        return content.strip()

    def chat_with_system(
        self,
        model: str,
        system: str,
        user: str,
        temperature: float = 0.2,
        format: Optional[str] = "json",
    ) -> str:
        """Convenience: one system message and one user message."""
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        return self.chat(model=model, messages=messages, temperature=temperature, format=format)

    def parse_json_response(self, content: str) -> Any:
        """Parse JSON from model output; tolerate markdown code blocks."""
        text = content.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines)
        return json.loads(text)


_ollama_client: Optional[OllamaClient] = None


def get_ollama_client() -> OllamaClient:
    global _ollama_client
    if _ollama_client is None:
        _ollama_client = OllamaClient()
    return _ollama_client
