"""LangGraph state definition for the deep research workflow."""

from __future__ import annotations

from typing import Any, TypedDict


class ResearchState(TypedDict):
    """State shared across all nodes in the research graph."""

    topic: str
    tasks: list[dict[str, Any]]
    search_results: dict[int, Any]
    draft_report: str
    final_report: str
    critic_score: float
    critic_feedback: str
    iteration: int
    error: str
