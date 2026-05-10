"""Critic agent: evaluate report quality and decide whether to iterate."""

from __future__ import annotations

import logging
from typing import Any

from app.agents.planner import _extract_json, call_llm
from app.config import settings
from app.prompts.templates import CRITIC_SYSTEM

logger = logging.getLogger(__name__)


async def critic_node(state: dict[str, Any]) -> dict[str, Any]:
    """Evaluate the draft report and provide a quality score + feedback."""
    report = state.get("draft_report", "")
    topic = state["topic"]

    if not report or len(report) < 100:
        logger.warning("Report too short (%d chars), skipping critic", len(report))
        return {
            "critic_score": 5.0,
            "critic_feedback": "",
            "final_report": report or "报告生成失败",
        }

    user_prompt = (
        f"# 研究主题：{topic}\n\n"
        f"# 待评估报告\n{report}\n\n"
        "请对以上报告进行严格评分并给出改进建议。"
    )

    messages = [
        {"role": "system", "content": CRITIC_SYSTEM},
        {"role": "user", "content": user_prompt},
    ]

    response = await call_llm(messages, agent_name="critic")
    logger.info("Critic response (truncated): %s", response[:300])

    result = _extract_json(response)

    overall_score = float(result.get("overall_score", 4.0))
    feedback = str(result.get("feedback", ""))
    suggested_queries = result.get("suggested_queries", [])

    if suggested_queries and isinstance(suggested_queries, list):
        queries_str = "；".join(suggested_queries)
        feedback = f"{feedback}\n建议补充检索：{queries_str}"

    threshold = settings.critic_score_threshold
    iteration = state.get("iteration", 0) + 1
    max_iter = settings.max_iterations

    logger.info(
        "Critic score=%.1f threshold=%.1f iteration=%d/%d",
        overall_score, threshold, iteration, max_iter,
    )

    needs_iteration = overall_score < threshold and iteration < max_iter

    return {
        "critic_score": overall_score,
        "critic_feedback": feedback if needs_iteration else "",
        "iteration": iteration,
        "final_report": report if not needs_iteration else "",
    }
