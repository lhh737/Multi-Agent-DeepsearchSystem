"""Executor agent: search the web and summarize findings per task."""

from __future__ import annotations

import logging
from typing import Any

from app.agents.planner import call_llm
from app.config import settings
from app.prompts.templates import EXECUTOR_SYSTEM
from app.tools.search import format_search_context, format_sources_list, search_web

logger = logging.getLogger(__name__)


async def _summarize_search(
    task: dict[str, Any],
    search_context: str,
    feedback: str = "",
) -> str:
    """Have the LLM analyze search results and produce a task summary."""
    feedback_note = f"\n\n上一轮评审反馈：{feedback}\n请根据反馈加深分析。" if feedback else ""

    user_prompt = (
        f"## 任务：{task['title']}\n"
        f"目标：{task['intent']}\n"
        f"检索关键词：{task['query']}\n"
        f"{feedback_note}\n"
        f"## 搜索上下文\n{search_context}\n\n"
        "请基于以上搜索上下文，为这个任务撰写分析总结。"
    )

    messages = [
        {"role": "system", "content": EXECUTOR_SYSTEM},
        {"role": "user", "content": user_prompt},
    ]

    return await call_llm(messages, agent_name="executor")


async def executor_node(state: dict[str, Any]) -> dict[str, Any]:
    """Execute search + summarization for each pending task."""
    tasks: list[dict[str, Any]] = state.get("tasks", [])
    feedback = state.get("critic_feedback", "")
    all_search_results: dict[int, Any] = dict(state.get("search_results", {}))

    updated_tasks = []
    for task in tasks:
        task = dict(task)
        updated_tasks.append(task)

        if task.get("status") == "completed" and not feedback:
            continue

        task_id = task["id"]
        query = task["query"]

        task["status"] = "in_progress"
        updated_tasks[task_id - 1]["status"] = "in_progress"

        # Perform web search (async, with Redis cache)
        search_result = await search_web(query)
        all_search_results[task_id] = search_result

        context = format_search_context(search_result)
        sources = format_sources_list(search_result)

        if not search_result.get("results"):
            task["status"] = "skipped"
            task["summary"] = "搜索未返回结果，任务跳过"
            task["sources"] = ""
            updated_tasks[task_id - 1] = task
            continue

        # Summarize
        try:
            summary = await _summarize_search(task, context, feedback)
        except Exception as exc:
            logger.exception("Summarization failed for task %d: %s", task_id, exc)
            summary = f"分析失败：{exc}"

        task["status"] = "completed"
        task["summary"] = summary
        task["sources"] = sources
        updated_tasks[task_id - 1] = task

    return {
        "tasks": updated_tasks,
        "search_results": all_search_results,
    }
