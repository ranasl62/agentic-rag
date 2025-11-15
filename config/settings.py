"""
Application settings loaded from environment variables.
Single source of truth for all service configuration.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-backed configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        env_ignore_empty=True,
    )

    # PostgreSQL
    postgres_host: str = Field(default="localhost", alias="POSTGRES_HOST")
    postgres_port: int = Field(default=5432, alias="POSTGRES_PORT")
    postgres_db: str = Field(default="agentic_rag", alias="POSTGRES_DB")
    postgres_user: str = Field(default="agentic_rag", alias="POSTGRES_USER")
    postgres_password: str = Field(default="", alias="POSTGRES_PASSWORD")

    # Qdrant
    qdrant_host: str = Field(default="localhost", alias="QDRANT_HOST")
    qdrant_port: int = Field(default=6333, alias="QDRANT_PORT")
    qdrant_grpc_port: int = Field(default=6334, alias="QDRANT_GRPC_PORT")

    # Ollama — one embed model; per-task chat models (all default to ollama_chat_model if unset)
    ollama_host: str = Field(default="http://localhost", alias="OLLAMA_HOST")
    ollama_port: int = Field(default=11434, alias="OLLAMA_PORT")
    ollama_embed_model: str = Field(
        default="nomic-embed-text", alias="OLLAMA_EMBED_MODEL"
    )
    ollama_chat_model: str = Field(default="llama3.2", alias="OLLAMA_CHAT_MODEL")
    ollama_search_answer_model: Optional[str] = Field(default=None, alias="OLLAMA_SEARCH_ANSWER_MODEL")
    ollama_query_model: Optional[str] = Field(default=None, alias="OLLAMA_QUERY_MODEL")
    ollama_summarize_model: Optional[str] = Field(default=None, alias="OLLAMA_SUMMARIZE_MODEL")
    ollama_compare_model: Optional[str] = Field(default=None, alias="OLLAMA_COMPARE_MODEL")
    ollama_verify_model: Optional[str] = Field(default=None, alias="OLLAMA_VERIFY_MODEL")

    # Chat provider: ollama | openai | anthropic (default ollama)
    chat_provider: str = Field(default="ollama", alias="CHAT_PROVIDER")
    # OpenAI (when CHAT_PROVIDER=openai)
    openai_api_key: Optional[str] = Field(default=None, alias="OPENAI_API_KEY")
    openai_chat_model: str = Field(default="gpt-4o-mini", alias="OPENAI_CHAT_MODEL")
    openai_base_url: Optional[str] = Field(default=None, alias="OPENAI_BASE_URL")  # e.g. for Azure
    # Anthropic (when CHAT_PROVIDER=anthropic), e.g. claude-3-5-sonnet, claude-3-opus
    anthropic_api_key: Optional[str] = Field(default=None, alias="ANTHROPIC_API_KEY")
    anthropic_chat_model: str = Field(default="claude-3-5-sonnet-20241022", alias="ANTHROPIC_CHAT_MODEL")

    # Embed provider: ollama | openai (default ollama). OpenAI dim often 1536; re-ingest if you switch.
    embed_provider: str = Field(default="ollama", alias="EMBED_PROVIDER")
    openai_embed_model: str = Field(default="text-embedding-3-small", alias="OPENAI_EMBED_MODEL")

    def ollama_model_for(self, task: str) -> str:
        """Return the Ollama chat model for a given task. Change models anytime via env."""
        m = {
            "search_answer": self.ollama_search_answer_model,
            "query": self.ollama_query_model,
            "summarize": self.ollama_summarize_model,
            "compare": self.ollama_compare_model,
            "verify": self.ollama_verify_model,
        }.get(task)
        return (m or self.ollama_chat_model).strip()

    def chat_model_for(self, task: str) -> str:
        """Return the chat model name for the current provider (Ollama, OpenAI, or Anthropic)."""
        provider = (self.chat_provider or "ollama").strip().lower()
        if provider == "openai":
            return (self.openai_chat_model or "gpt-4o-mini").strip()
        if provider == "anthropic":
            return (self.anthropic_chat_model or "claude-3-5-sonnet-20241022").strip()
        return self.ollama_model_for(task)

    # Redis
    redis_host: str = Field(default="localhost", alias="REDIS_HOST")
    redis_port: int = Field(default=6379, alias="REDIS_PORT")
    redis_db: int = Field(default=0, alias="REDIS_DB")

    # App
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    metrics_enabled: bool = Field(default=True, alias="METRICS_ENABLED")
    api_host: str = Field(default="0.0.0.0", alias="API_HOST")
    api_port: int = Field(default=8000, alias="API_PORT")

    # Auth (Phase 1: API key per tenant)
    require_auth: bool = Field(default=True, alias="REQUIRE_AUTH")
    default_tenant_slug: str = Field(default="default", alias="DEFAULT_TENANT_SLUG")

    # Phase 2: Rate limiting (per tenant per minute; 0 = no limit for that endpoint)
    rate_limit_enabled: bool = Field(default=True, alias="RATE_LIMIT_ENABLED")
    rate_limit_search_per_min: int = Field(default=100, alias="RATE_LIMIT_SEARCH_PER_MIN")
    rate_limit_query_per_min: int = Field(default=20, alias="RATE_LIMIT_QUERY_PER_MIN")
    rate_limit_upload_per_min: int = Field(default=5, alias="RATE_LIMIT_UPLOAD_PER_MIN")
    rate_limit_compare_per_min: int = Field(default=30, alias="RATE_LIMIT_COMPARE_PER_MIN")
    rate_limit_summarize_per_min: int = Field(default=30, alias="RATE_LIMIT_SUMMARIZE_PER_MIN")
    rate_limit_list_per_min: int = Field(default=60, alias="RATE_LIMIT_LIST_PER_MIN")
    rate_limit_ip_per_min: int = Field(default=0, alias="RATE_LIMIT_IP_PER_MIN")  # 0 = disabled

    # Phase 2: Caching (TTL in seconds; 0 = disabled)
    cache_enabled: bool = Field(default=True, alias="CACHE_ENABLED")
    cache_search_ttl_seconds: int = Field(default=300, alias="CACHE_SEARCH_TTL_SECONDS")
    cache_query_ttl_seconds: int = Field(default=120, alias="CACHE_QUERY_TTL_SECONDS")

    # Ingestion
    upload_dir: str = Field(default="./data/uploads", alias="UPLOAD_DIR")
    processed_dir: str = Field(default="./data/processed", alias="PROCESSED_DIR")

    @property
    def postgres_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def postgres_url_sync(self) -> str:
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def ollama_base_url(self) -> str:
        base = self.ollama_host.rstrip("/")
        if "://" not in base:
            base = f"http://{base}"
        return f"{base}:{self.ollama_port}"

    @property
    def embed_dimension(self) -> int:
        """Vector size for Qdrant; 1536 for OpenAI, 768 for Ollama (nomic)."""
        if (self.embed_provider or "").strip().lower() == "openai":
            return 1536
        return 768

    @property
    def redis_url(self) -> str:
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"

    # Phase 3: Async ingestion (Celery)
    celery_broker_url: Optional[str] = Field(default=None, alias="CELERY_BROKER_URL")
    ingest_job_status_ttl_seconds: int = Field(default=86400, alias="INGEST_JOB_STATUS_TTL_SECONDS")
    ingest_async_default: bool = Field(default=False, alias="INGEST_ASYNC_DEFAULT")

    @property
    def celery_broker_url_or_redis(self) -> str:
        return self.celery_broker_url or self.redis_url


@lru_cache
def get_settings() -> Settings:
    return Settings()
