"""Reporter agent: compile all task summaries into a structured report."""

from __future__ import annotations

import logging
from typing import Any

from app.agents.planner import call_llm
from app.prompts.templates import REPORTER_SYSTEM

logger = logging.getLogger(__name__)


async def reporter_node(state: dict[str, Any]) -> dict[str, Any]:
    """Consolidate all task summaries into a final structured report."""
    tasks: list[dict[str, Any]] = state.get("tasks", [])
    topic = state["topic"]

    tasks_block_parts = []
    for task in tasks:
        summary = task.get("summary", "暂未完成")
        sources = task.get("sources", "暂无来源")
        tasks_block_parts.append(
            f"### 子任务 {task['id']}：{task['title']}\n"
            f"意图：{task['intent']}\n"
            f"分析：\n{summary}\n"
            f"来源：\n{sources}\n"
        )

    tasks_block = "\n---\n".join(tasks_block_parts)

    user_prompt = (
        f"# 研究主题：{topic}\n\n"
        f"# 子任务分析结果\n{tasks_block}\n\n"
        "请整合以上所有子任务分析，撰写一份结构化的最终研究报告。"
    )

    messages = [
        {"role": "system", "content": REPORTER_SYSTEM},
        {"role": "user", "content": user_prompt},
    ]

    report = await call_llm(messages, agent_name="reporter")
    logger.info("Reporter produced report of %d chars", len(report))

    return {"draft_report": report}
