"""Web search tools: Tavily (primary) + DuckDuckGo (fallback) with Redis cache."""

from __future__ import annotations

import logging
import time
from typing import Any

from app.cache.redis_cache import get_cached_search, set_cached_search
from app.config import settings

logger = logging.getLogger(__name__)


async def search_web(query: str, max_results: int | None = None) -> dict[str, Any]:
    """Execute web search with Redis cache. Prefers Tavily, falls back to DuckDuckGo."""
    if max_results is None:
        max_results = settings.max_search_results

    # Check cache first
    cached = await get_cached_search(query)
    if cached:
        cached["_from_cache"] = True
        return cached

    api = settings.search_api.lower()
    t0 = time.monotonic()

    if api == "tavily" and settings.tavily_api_key:
        result = await _search_tavily(query, max_results)
    elif api == "duckduckgo":
        result = _search_duckduckgo(query, max_results)
    else:
        result = _search_duckduckgo(query, max_results)

    elapsed = (time.monotonic() - t0) * 1000
    result["_from_cache"] = False
    result["_elapsed_ms"] = round(elapsed, 1)

    # Cache successful results
    if result.get("results"):
        await set_cached_search(query, result)

    return result


async def _search_tavily(query: str, max_results: int) -> dict[str, Any]:
    """Search using Tavily API."""
    try:
        from tavily import TavilyClient

        client = TavilyClient(api_key=settings.tavily_api_key)
        response = client.search(
            query=query,
            max_results=max_results,
            search_depth="advanced",
            include_answer=True,
        )
        results = []
        for r in response.get("results", []):
            results.append({
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "content": r.get("content", ""),
            })
        return {
            "results": results,
            "answer": response.get("answer", ""),
            "backend": "tavily",
        }
    except Exception as exc:
        logger.warning("Tavily search failed: %s, falling back to DuckDuckGo", exc)
        return _search_duckduckgo(query, max_results)


def _search_duckduckgo(query: str, max_results: int) -> dict[str, Any]:
    """Search using DuckDuckGo (free, no API key)."""
    try:
        from ddgs import DDGS

        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                results.append({
                    "title": r.get("title", ""),
                    "url": r.get("href", ""),
                    "content": r.get("body", ""),
                })
        return {"results": results, "answer": None, "backend": "duckduckgo"}
    except Exception as exc:
        logger.exception("DuckDuckGo search failed: %s", exc)
        return {"results": [], "answer": None, "backend": "duckduckgo", "error": str(exc)}


def format_search_context(search_result: dict[str, Any]) -> str:
    """Format search results into a readable context string for the LLM."""
    parts: list[str] = []

    answer = search_result.get("answer")
    if answer:
        parts.append(f"## AI 摘要\n{answer}\n")

    results = search_result.get("results", [])
    if results:
        parts.append("## 搜索结果\n")
        for i, r in enumerate(results, 1):
            title = r.get("title", "无标题")
            url = r.get("url", "")
            content = r.get("content", "")
            parts.append(f"### [{i}] {title}")
            if url:
                parts.append(f"URL: {url}")
            parts.append(f"{content}\n")

    return "\n".join(parts) if parts else "未获取到任何搜索结果"


def format_sources_list(search_result: dict[str, Any]) -> str:
    """Return a compact bullet list of sources."""
    results = search_result.get("results", [])
    if not results:
        return "暂无来源"
    lines = []
    for r in results:
        title = r.get("title", "无标题")
        url = r.get("url", "")
        lines.append(f"* [{title}]({url})")
    return "\n".join(lines)
