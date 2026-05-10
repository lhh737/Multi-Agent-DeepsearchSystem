"""Planner agent: decompose a research topic into sub-tasks."""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any

from app.config import settings
from app.tracing.langsmith import trace_llm_call

logger = logging.getLogger(__name__)


async def call_llm(messages: list[dict[str, Any]], *, agent_name: str = "") -> str:
    """Call the configured LLM and return the content string."""
    from openai import AsyncOpenAI

    client = AsyncOpenAI(
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
        timeout=settings.llm_timeout,
    )
    t0 = time.monotonic()
    response = await client.chat.completions.create(
        model=settings.llm_model_id,
        messages=messages,
        temperature=settings.llm_temperature,
    )
    duration_ms = (time.monotonic() - t0) * 1000
    content = response.choices[0].message.content or ""

    trace_llm_call(
        agent_name or "planner",
        messages,
        content,
        model=settings.llm_model_id,
        duration_ms=duration_ms,
    )

    return content


def _extract_json(text: str) -> dict[str, Any]:
    """Extract JSON object from text, handling markdown code blocks."""
    match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if match:
        text = match.group(1)

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            pass

    start = text.find("[")
    end = text.rfind("]")
    if start != -1 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            pass

    return {}


async def planner_node(state: dict[str, Any]) -> dict[str, Any]:
    """Break the research topic into 3-5 complementary sub-tasks."""
    from app.prompts.templates import PLANNER_SYSTEM

    topic = state["topic"]
    iteration = state.get("iteration", 0)
    critic_feedback = state.get("critic_feedback", "")

    feedback_instruction = ""
    if iteration > 0 and critic_feedback:
        feedback_instruction = (
            f"\n\n这是第 {iteration + 1} 轮迭代。上一轮评审反馈：\n{critic_feedback}\n"
            "请根据反馈调整任务规划，补充缺失角度或加深薄弱环节。"
        )

    user_prompt = (
        f"研究主题：{topic}{feedback_instruction}\n"
        "请将此主题拆解为 3~5 个互补的子任务。"
    )

    messages = [
        {"role": "system", "content": PLANNER_SYSTEM},
        {"role": "user", "content": user_prompt},
    ]

    response = await call_llm(messages, agent_name="planner")
    logger.info("Planner response (truncated): %s", response[:300])

    payload = _extract_json(response)
    raw_tasks = payload.get("tasks", []) if isinstance(payload, dict) else []

    if not raw_tasks:
        logger.warning("Planner produced no tasks, using fallback")
        raw_tasks = [
            {"title": "主题全景分析", "intent": "全面收集主题的核心信息与最新进展", "query": topic}
        ]

    tasks = []
    for i, t in enumerate(raw_tasks):
        tasks.append({
            "id": i + 1,
            "title": str(t.get("title", f"任务{i + 1}")),
            "intent": str(t.get("intent", "")),
            "query": str(t.get("query", topic)),
            "status": "pending",
            "summary": "",
            "sources": "",
        })

    return {"tasks": tasks, "iteration": state.get("iteration", 0)}
