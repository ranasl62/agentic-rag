"""
Unified chat client: Ollama, OpenAI, or Anthropic (Claude/Opus).
Provider and model are set via env (CHAT_PROVIDER, OPENAI_*, ANTHROPIC_*).
"""
from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from config import get_settings


class BaseChatClient(ABC):
    """Abstract chat interface used by agents and search."""

    @abstractmethod
    def chat(
        self,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.2,
        format: Optional[str] = "json",
    ) -> str:
        """Return assistant message content."""
        ...

    def chat_with_system(
        self,
        model: str,
        system: str,
        user: str,
        temperature: float = 0.2,
        format: Optional[str] = "json",
    ) -> str:
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        return self.chat(model=model, messages=messages, temperature=temperature, format=format)

    @staticmethod
    def parse_json_response(content: str) -> Any:
        text = content.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines)
        return json.loads(text)


class OllamaChatAdapter(BaseChatClient):
    """Delegates to existing Ollama client."""

    def __init__(self) -> None:
        from src.llm.ollama_client import get_ollama_client
        self._client = get_ollama_client()

    def chat(
        self,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.2,
        format: Optional[str] = "json",
    ) -> str:
        return self._client.chat(model=model, messages=messages, temperature=temperature, format=format)


class OpenAIChatAdapter(BaseChatClient):
    """OpenAI API (gpt-4o, gpt-4o-mini, etc.)."""

    def __init__(self) -> None:
        s = get_settings()
        if not (s.openai_api_key or "").strip():
            raise ValueError("OPENAI_API_KEY is required when CHAT_PROVIDER=openai")
        self._api_key = s.openai_api_key.strip()
        self._base_url = (s.openai_base_url or "https://api.openai.com/v1").rstrip("/")

    def chat(
        self,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.2,
        format: Optional[str] = "json",
    ) -> str:
        import httpx
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "stream": False,
        }
        if format == "json":
            payload["response_format"] = {"type": "json_object"}
        with httpx.Client(timeout=120.0) as client:
            resp = client.post(
                f"{self._base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"},
                json=payload,
            )
            resp.raise_for_status()
        data = resp.json()
        content = (data.get("choices") or [{}])[0].get("message", {}).get("content") or ""
        return content.strip()


class AnthropicChatAdapter(BaseChatClient):
    """Anthropic API (Claude 3.5 Sonnet, Claude 3 Opus, etc.)."""

    def __init__(self) -> None:
        s = get_settings()
        if not (s.anthropic_api_key or "").strip():
            raise ValueError("ANTHROPIC_API_KEY is required when CHAT_PROVIDER=anthropic")
        self._api_key = s.anthropic_api_key.strip()

    def chat(
        self,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.2,
        format: Optional[str] = "json",
    ) -> str:
        import httpx
        # Anthropic: system is separate; user/assistant alternate
        system = ""
        body_messages: List[Dict[str, str]] = []
        for m in messages:
            role = (m.get("role") or "user").lower()
            content = (m.get("content") or "").strip()
            if role == "system":
                system = content
            else:
                body_messages.append({"role": role, "content": content})
        if not body_messages:
            return ""
        payload = {
            "model": model,
            "max_tokens": 4096,
            "temperature": temperature,
            "messages": body_messages,
        }
        if system:
            payload["system"] = system
        if format == "json":
            payload["system"] = (payload.get("system") or "") + "\n\nRespond with valid JSON only, no markdown."
        with httpx.Client(timeout=120.0) as client:
            resp = client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": self._api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            resp.raise_for_status()
        data = resp.json()
        for b in (data.get("content") or []):
            if b.get("type") == "text":
                return (b.get("text") or "").strip()
        return ""


_chat_client: Optional[BaseChatClient] = None


def get_chat_client() -> BaseChatClient:
    """Return the chat client for the configured provider (ollama, openai, anthropic)."""
    global _chat_client
    if _chat_client is not None:
        return _chat_client
    s = get_settings()
    provider = (s.chat_provider or "ollama").strip().lower()
    if provider == "openai":
        _chat_client = OpenAIChatAdapter()
    elif provider == "anthropic":
        _chat_client = AnthropicChatAdapter()
    else:
        _chat_client = OllamaChatAdapter()
    return _chat_client
