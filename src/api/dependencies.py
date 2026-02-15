"""
FastAPI dependencies: session, storage, LLM, tools, orchestrator.
"""
from __future__ import annotations

from typing import Dict

from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from src.storage.postgres_client import session_scope
from src.storage.qdrant_client import get_qdrant_storage, QdrantStorage
from src.storage.redis_client import get_redis_client
from src.llm.chat_client import get_chat_client
from src.llm.embeddings import get_embedding_service
from src.llm.prompt_templates import PromptTemplates
from src.tools.search_tools import (
    SearchSectionsTool,
    FindSameSectionAcrossEditionsTool,
    ListAvailableEditionsTool,
)
from src.tools.matching_tools import MatchSectionsTool
from src.tools.comparison_tools import CompareSectionsTool
from src.tools.summarization_tools import SummarizeSectionTool, SummarizeDifferencesTool
from src.agents.query_understanding_agent import QueryUnderstandingAgent
from src.agents.retrieval_planning_agent import RetrievalPlanningAgent
from src.agents.comparison_agent import ComparisonAgent
from src.agents.summarization_agent import SummarizationAgent
from src.agents.verification_agent import VerificationAgent
from src.agents.orchestrator import Orchestrator


def get_qdrant() -> QdrantStorage:
    return get_qdrant_storage()


def get_tools_dict() -> Dict[str, object]:
    """Build tool instances with injected deps. Keys = tool name for orchestrator."""
    qdrant = get_qdrant_storage()
    embedding = get_embedding_service()
    chat_client = get_chat_client()
    prompts = PromptTemplates()
    search_tool = SearchSectionsTool(qdrant, embedding, session_scope)
    find_same_tool = FindSameSectionAcrossEditionsTool(qdrant, session_scope)
    list_editions_tool = ListAvailableEditionsTool(session_scope)
    match_tool = MatchSectionsTool(session_scope)
    compare_tool = CompareSectionsTool()
    sum_section_tool = SummarizeSectionTool(chat_client, prompts)
    sum_diff_tool = SummarizeDifferencesTool(chat_client, prompts)
    return {
        "search_sections": search_tool,
        "find_same_section_across_editions": find_same_tool,
        "list_available_editions": list_editions_tool,
        "match_sections": match_tool,
        "compare_sections": compare_tool,
        "summarize_section": sum_section_tool,
        "summarize_differences": sum_diff_tool,
    }


def get_orchestrator() -> Orchestrator:
    chat_client = get_chat_client()
    prompts = PromptTemplates()
    tools = get_tools_dict()
    list_tool = tools["list_available_editions"]
    return Orchestrator(
        query_agent=QueryUnderstandingAgent(chat_client, prompts),
        retrieval_agent=RetrievalPlanningAgent(chat_client, prompts),
        comparison_agent=ComparisonAgent(chat_client, prompts),
        summarization_agent=SummarizationAgent(chat_client, prompts),
        verification_agent=VerificationAgent(chat_client, prompts),
        tools=tools,
        list_editions_tool=list_tool,
    )
