#!/usr/bin/env python3
"""
Interactive chatbot for the Agentic RAG API (Phase 1).
Uses POST /query for each user message; supports tenant auth via X-API-Key.

Usage:
  # With default tenant (REQUIRE_AUTH=false):
  uv run python -m scripts.chat

  # With API key:
  AGENT_API_KEY=your-key uv run python -m scripts.chat

  # Custom base URL (default 8080 when using Docker + Nginx):
  API_BASE_URL=http://localhost:8080 uv run python -m scripts.chat

Commands in chat:
  /quit or /exit  - exit
  /help           - show help
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx

BASE = os.environ.get("API_BASE_URL", "http://localhost:8080")
API_KEY = os.environ.get("AGENT_API_KEY", "")


def headers():
    h = {"Content-Type": "application/json"}
    if API_KEY:
        h["X-API-Key"] = API_KEY
    return h


def query_api(message: str, skip_verification: bool = True) -> tuple[str, list, bool]:
    """Call POST /query. Returns (response_text, citations, verified)."""
    try:
        with httpx.Client(timeout=120.0) as client:
            r = client.post(
                f"{BASE}/query",
                json={"query": message, "skip_verification": skip_verification},
                headers=headers(),
            )
    except httpx.ConnectError as e:
        return f"Connection error: {e}. Is the API running at {BASE}?", [], False
    except Exception as e:
        return f"Error: {e}", [], False

    if r.status_code == 401:
        return "Unauthorized (invalid or missing API key). Set AGENT_API_KEY or run with REQUIRE_AUTH=false.", [], False
    if r.status_code == 503:
        return r.json().get("detail", "Service unavailable."), [], False
    if r.status_code != 200:
        return f"API returned {r.status_code}: {r.text[:500]}", [], False

    data = r.json()
    return (
        data.get("response", ""),
        data.get("citations", []),
        data.get("verified", False),
    )


def main():
    print("Agentic RAG Chat (Phase 1)")
    print(f"  API: {BASE}")
    print(f"  Auth: {'X-API-Key' if API_KEY else 'none (default tenant)'}")
    print("  Commands: /quit, /exit, /help")
    print()

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye.")
            break
        if not user_input:
            continue
        if user_input.lower() in ("/quit", "/exit", "quit", "exit"):
            print("Bye.")
            break
        if user_input.lower() == "/help":
            print("  Ask questions about your manuals. The agent will search, compare, or summarize as needed.")
            print("  /quit or /exit to exit.")
            continue

        print("Agent: ", end="", flush=True)
        response, citations, verified = query_api(user_input)
        print(response)
        if citations:
            print(f"  [Citations: {len(citations)}]")
        if verified:
            print("  [Verified against source]")
        print()

    sys.exit(0)


if __name__ == "__main__":
    main()
