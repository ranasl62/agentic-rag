"""
Base interface for all agent tools. Tools are deterministic and testable.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from pydantic import BaseModel


@dataclass
class ToolResult:
    """Strict output schema for every tool."""

    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    citations: list[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "citations": self.citations,
        }


class ToolInput(BaseModel):
    """Base for tool input schemas; subclasses define strict fields."""

    tenant_id: Optional[str] = None  # Set by orchestrator for tenant-scoped tools


class BaseTool(ABC):
    """All tools implement name, description, input schema, and execute (async)."""

    name: str = ""
    description: str = ""
    input_schema: type[BaseModel] = ToolInput

    @abstractmethod
    async def execute(self, **kwargs: Any) -> ToolResult:
        """Run the tool. Inputs must match input_schema."""
        ...

    async def run(self, **kwargs: Any) -> ToolResult:
        """Validate inputs against schema then execute."""
        try:
            validated = self.input_schema(**kwargs)
            return await self.execute(**validated.model_dump())
        except Exception as e:
            return ToolResult(success=False, error=str(e))
