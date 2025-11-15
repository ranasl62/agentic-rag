"""
Orchestrator: Query Understanding → Retrieval Planning → Tool Execution → Comparison/Summary → Verification.
Agents and tools are invoked in order; no direct agent-to-agent calls.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from uuid import UUID

from src.agents.base_agent import BaseAgent
from src.agents.query_understanding_agent import QueryUnderstandingAgent
from src.agents.retrieval_planning_agent import RetrievalPlanningAgent
from src.agents.comparison_agent import ComparisonAgent
from src.agents.summarization_agent import SummarizationAgent
from src.agents.verification_agent import VerificationAgent
from src.tools.base_tool import BaseTool, ToolResult


class Orchestrator:
    """
    Coordinates agents and tools. Build with injected dependencies (clients, tools).
    """

    def __init__(
        self,
        query_agent: QueryUnderstandingAgent,
        retrieval_agent: RetrievalPlanningAgent,
        comparison_agent: ComparisonAgent,
        summarization_agent: SummarizationAgent,
        verification_agent: VerificationAgent,
        tools: Dict[str, BaseTool],
        list_editions_tool: BaseTool,
    ) -> None:
        self._query_agent = query_agent
        self._retrieval_agent = retrieval_agent
        self._comparison_agent = comparison_agent
        self._summarization_agent = summarization_agent
        self._verification_agent = verification_agent
        self._tools = tools
        self._list_editions_tool = list_editions_tool

    async def run(
        self,
        query: str,
        available_books: str = "",
        *,
        skip_verification: bool = False,
        tenant_id: Optional[UUID] = None,
    ) -> Dict[str, Any]:
        """
        Full pipeline: understand query → plan retrieval → run tools → compare/summarize → verify.
        """
        steps: List[Dict[str, Any]] = []
        citations: List[Dict[str, Any]] = []
        final_response: Optional[str] = None
        source_context = ""
        tenant_id_str = str(tenant_id) if tenant_id else None

        # 1. List available books if empty (for query understanding)
        if not available_books:
            list_result = await self._list_editions_tool.run(tenant_id=tenant_id_str)
            if list_result.success and list_result.data:
                books = list_result.data.get("books", [])
                available_books = "\n".join(
                    f"- {b.get('title')} (id: {b.get('book_id')}) editions: {[e.get('edition_name') for e in b.get('editions', [])]}"
                    for b in books
                )
        steps.append({"step": "list_editions", "data": available_books[:500]})

        # 2. Query Understanding
        intent = await self._query_agent.run(query=query, available_books=available_books)
        steps.append({"step": "query_understanding", "intent": intent})
        if intent.get("confidence", 0) < 0.5 and intent.get("ambiguity_note"):
            return {
                "response": f"I'm not sure I understood. {intent.get('ambiguity_note')}",
                "steps": steps,
                "citations": [],
                "verified": False,
            }

        # 3. Retrieval Planning
        plan = await self._retrieval_agent.run(query_intent=intent, query=query)
        steps.append({"step": "retrieval_plan", "plan": plan})

        # 4. Execute plan steps (tools)
        tool_results: List[ToolResult] = []
        plan_steps = plan.get("steps", [])[:5]
        # If chat failed (plan has error), ensure we have at least one search step with the user query
        if (plan.get("error") or intent.get("error")) and not any(
            s.get("parameters", {}).get("query") for s in plan_steps if s.get("tool") == "search_sections"
        ):
            plan_steps = [{"tool": "search_sections", "parameters": {"query": query.strip() or "content"}, "reasoning": "fallback"}]
        for step in plan_steps:
            tool_name = step.get("tool")
            params = dict(step.get("parameters", {}))
            if not tool_name or tool_name not in self._tools:
                continue
            # search_sections requires "query"; LLM often returns "book"/"edition" (names) instead of book_id/edition_id (UUIDs).
            if tool_name == "search_sections":
                raw = step.get("parameters", {})
                search_query = (raw.get("query") or query or "content").strip() or "content"
                limit = raw.get("limit", 10)
                if limit is None or not (1 <= limit <= 50):
                    limit = 10
                params = {"query": search_query, "limit": limit}
                for key in ("book_id", "edition_id", "score_threshold"):
                    if raw.get(key) is not None:
                        params[key] = raw[key]
            if tenant_id_str is not None:
                params["tenant_id"] = tenant_id_str
            tool = self._tools[tool_name]
            result = await tool.run(**params)
            tool_results.append(result)
            if result.citations:
                citations.extend(result.citations)
            if result.data:
                source_context += str(result.data)[:4000] + "\n"
            steps.append({"step": f"tool_{tool_name}", "success": result.success, "data_keys": list((result.data or {}).keys())})
        # If search_sections failed or returned no context, run one direct semantic search so the user gets results
        if not source_context and "search_sections" in self._tools:
            fallback_params = {"query": (query or "content").strip(), "limit": 10}
            if tenant_id_str is not None:
                fallback_params["tenant_id"] = tenant_id_str
            fallback = await self._tools["search_sections"].run(**fallback_params)
            tool_results.append(fallback)
            if fallback.citations:
                citations.extend(fallback.citations)
            if fallback.data:
                source_context += str(fallback.data)[:4000] + "\n"
            steps.append({"step": "tool_search_sections_fallback", "success": fallback.success, "data_keys": list((fallback.data or {}).keys())})

        # 5. Decide: compare vs summarize
        intent_type = intent.get("intent_type", "search")
        sections_for_comparison = []
        for tr in tool_results:
            if tr.data and "sections" in tr.data:
                sections_for_comparison = tr.data["sections"]
                break
            if tr.data and "results" in tr.data:
                sections_for_comparison = tr.data["results"]
                break

        if intent_type == "compare" and len(sections_for_comparison) >= 2:
            comp_result = await self._comparison_agent.run(sections_for_comparison=sections_for_comparison)
            final_response = comp_result.get("summary", "") or str(comp_result.get("dimensions", []))
            if comp_result.get("citations"):
                citations = comp_result["citations"]
            steps.append({"step": "comparison", "summary_length": len(final_response)})
        elif intent_type == "summarize" and sections_for_comparison:
            if len(sections_for_comparison) == 1:
                s = sections_for_comparison[0]
                sum_result = await self._summarization_agent.run(
                    summary_type="section",
                    content=s.get("content_text", s.get("content_preview", "")),
                    max_length=300,
                )
                final_response = sum_result.get("content", "")
            else:
                sum_result = await self._summarization_agent.run(
                    summary_type="differences",
                    content="\n\n".join(
                        f"Edition: {x.get('edition_id')}\n{x.get('content_text', x.get('content_preview', ''))}"
                        for x in sections_for_comparison
                    ),
                    max_length=500,
                )
                final_response = sum_result.get("content", "")
            steps.append({"step": "summarization", "summary_length": len(final_response or "")})
        else:
            # Default: return search/retrieval result
            final_response = "No comparison or summary requested; here are the retrieved sections."
            for tr in tool_results:
                if tr.success and tr.data:
                    results = tr.data.get("results", tr.data.get("sections", []))
                    if results:
                        parts = []
                        for r in results[:10]:
                            content = r.get("content_text") or r.get("content_preview") or r.get("text", "")
                            title = r.get("section_title") or r.get("location_path") or r.get("title", "")
                            if title:
                                parts.append(f"**{title}**\n{content[:400]}")
                            else:
                                parts.append(str(content)[:400])
                        if parts:
                            final_response += "\n\n" + "\n\n---\n\n".join(parts)
                    break

        if not final_response:
            final_response = "I couldn't produce a comparison or summary from the retrieved sections."

        # 6. Verification (optional)
        verified = False
        if not skip_verification and source_context and final_response:
            ver = await self._verification_agent.run(response=final_response, source_context=source_context[:6000])
            verified = ver.get("is_grounded", False)
            steps.append({"step": "verification", "is_grounded": verified})
            if ver.get("unsupported_claims"):
                final_response += "\n\n[Note: Some claims could not be verified against the source.]"

        return {
            "response": final_response,
            "steps": steps,
            "citations": citations[:50],
            "verified": verified,
        }
