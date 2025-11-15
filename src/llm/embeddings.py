"""
Embedding service: Ollama or OpenAI. Switch via EMBED_PROVIDER.
Note: OpenAI uses 1536 dim (text-embedding-3-small); re-ingest if you switch from Ollama (768).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from config import get_settings


class BaseEmbeddingService(ABC):
    @abstractmethod
    def embed(self, text: str) -> List[float]:
        ...

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        return [self.embed(t) for t in texts]

    @property
    @abstractmethod
    def dimension(self) -> int:
        ...


class OllamaEmbeddingService(BaseEmbeddingService):
    """Generate embeddings via Ollama (e.g. nomic-embed-text, 768 dim)."""

    def __init__(self, base_url: Optional[str] = None, model: Optional[str] = None) -> None:
        s = get_settings()
        self._base_url = (base_url or s.ollama_base_url).rstrip("/")
        self._model = model or s.ollama_embed_model

    def _url(self, path: str) -> str:
        return f"{self._base_url}{path}"

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10), reraise=True)
    def embed(self, text: str) -> List[float]:
        with httpx.Client(timeout=60.0) as client:
            resp = client.post(
                self._url("/api/embeddings"),
                json={"model": self._model, "prompt": text},
            )
            resp.raise_for_status()
        data = resp.json()
        return data.get("embedding") or []

    @property
    def dimension(self) -> int:
        return len(self.embed("."))


class OpenAIEmbeddingService(BaseEmbeddingService):
    """OpenAI embeddings (e.g. text-embedding-3-small, 1536 dim)."""

    def __init__(self) -> None:
        s = get_settings()
        if not (s.openai_api_key or "").strip():
            raise ValueError("OPENAI_API_KEY is required when EMBED_PROVIDER=openai")
        self._api_key = s.openai_api_key.strip()
        self._model = s.openai_embed_model or "text-embedding-3-small"
        self._base_url = (s.openai_base_url or "https://api.openai.com/v1").rstrip("/")
        self._dimension = 1536  # text-embedding-3-small; override if using another model

    def embed(self, text: str) -> List[float]:
        with httpx.Client(timeout=60.0) as client:
            resp = client.post(
                f"{self._base_url}/embeddings",
                headers={"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"},
                json={"model": self._model, "input": text[:8191]},
            )
            resp.raise_for_status()
        data = resp.json()
        for item in (data.get("data") or []):
            if "embedding" in item:
                return item["embedding"]
        return []

    @property
    def dimension(self) -> int:
        return self._dimension


# Backward compatibility: EmbeddingService = Ollama when embed_provider not set
EmbeddingService = OllamaEmbeddingService

_embedding_service: Optional[BaseEmbeddingService] = None


def get_embedding_service() -> BaseEmbeddingService:
    global _embedding_service
    if _embedding_service is not None:
        return _embedding_service
    s = get_settings()
    provider = (s.embed_provider or "ollama").strip().lower()
    if provider == "openai":
        _embedding_service = OpenAIEmbeddingService()
    else:
        _embedding_service = OllamaEmbeddingService()
    return _embedding_service
