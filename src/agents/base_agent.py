"""
Base agent: single responsibility, tool-based communication, explicit reasoning.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from src.tools.base_tool import ToolResult


class BaseAgent(ABC):
    """Agents use tools and LLM; they do not call each other directly."""

    name: str = ""

    @abstractmethod
    async def run(self, **inputs: Any) -> Dict[str, Any]:
        """Execute agent logic. Returns structured result (e.g. intent, plan, summary)."""
        ...

    def _tool_result_to_dict(self, result: ToolResult) -> Dict[str, Any]:
        return result.to_dict()
