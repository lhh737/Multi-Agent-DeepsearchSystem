"""Build the LangGraph state graph for the deep research workflow."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from langgraph.graph import END, StateGraph

from app.agents.critic import critic_node
from app.agents.executor import executor_node
from app.agents.planner import planner_node
from app.agents.reporter import reporter_node
from app.config import settings
from app.graph.state import ResearchState
from app.persistence.repository import create_session, save_tasks, update_session
from app.tracing.langsmith import setup_langsmith, trace_agent_step

logger = logging.getLogger(__name__)


def _should_continue(state: ResearchState) -> str:
    """Route: decide whether to iterate (back to executor) or finish."""
    if state.get("error"):
        return "end"

    score = state.get("critic_score", 0)
    iteration = state.get("iteration", 0)

    if score >= settings.critic_score_threshold or iteration >= settings.max_iterations:
        logger.info("Research complete: score=%.1f iteration=%d", score, iteration)
        return "end"

    logger.info("Continuing iteration: score=%.1f iteration=%d", score, iteration)
    return "executor"


def build_research_graph() -> StateGraph:
    """Construct the LangGraph StateGraph for multi-agent deep research."""
    workflow = StateGraph(ResearchState)

    workflow.add_node("planner", planner_node)
    workflow.add_node("executor", executor_node)
    workflow.add_node("reporter", reporter_node)
    workflow.add_node("critic", critic_node)

    workflow.set_entry_point("planner")

    workflow.add_edge("planner", "executor")
    workflow.add_edge("executor", "reporter")
    workflow.add_edge("reporter", "critic")

    workflow.add_conditional_edges(
        "critic",
        _should_continue,
        {"executor": "executor", "end": END},
    )

    return workflow


_graph: Any = None


def _get_graph():
    global _graph
    if _graph is None:
        setup_langsmith()
        _graph = build_research_graph().compile()
    return _graph


async def run_research(topic: str) -> dict[str, Any]:
    """Run the research graph (non-streaming) with persistence."""
    session_id = await create_session(topic)

    initial: ResearchState = {
        "topic": topic,
        "tasks": [],
        "search_results": {},
        "draft_report": "",
        "final_report": "",
        "critic_score": 0.0,
        "critic_feedback": "",
        "iteration": 0,
        "error": "",
    }

    try:
        result = dict(await _get_graph().ainvoke(initial))
    except Exception as exc:
        logger.exception("Research failed")
        await update_session(session_id, status="failed", error=str(exc))
        raise

    # Persist results
    final_report = result.get("final_report") or result.get("draft_report", "")
    tasks = result.get("tasks", [])

    await save_tasks(session_id, tasks)
    await update_session(
        session_id,
        report=final_report,
        critic_score=result.get("critic_score", 0),
        iterations=result.get("iteration", 0),
        status="completed",
    )

    result["session_id"] = session_id
    return result


async def run_research_stream(
    topic: str,
    event_queue: asyncio.Queue,
) -> dict[str, Any]:
    """Run the research graph with SSE streaming + persistence."""

    def emit(event_type: str, data: dict[str, Any] | None = None):
        try:
            event_queue.put_nowait({"type": event_type, "data": data or {}})
        except asyncio.QueueFull:
            pass

    emit("status", {"message": "正在初始化 LangGraph 多智能体协作系统…"})

    # Create session in Postgres
    session_id = await create_session(topic)
    emit("status", {"message": f"研究会话已创建：{session_id[:8]}…"})

    initial: ResearchState = {
        "topic": topic,
        "tasks": [],
        "search_results": {},
        "draft_report": "",
        "final_report": "",
        "critic_score": 0.0,
        "critic_feedback": "",
        "iteration": 0,
        "error": "",
    }

    final: ResearchState = initial  # type: ignore

    try:
        async for event in _get_graph().astream(initial):
            node_name = list(event.keys())[0]
            node_output = event[node_name]

            # Trace to LangSmith
            trace_agent_step(
                node_name,
                {"topic": topic, "node": node_name},
                {k: str(v)[:500] for k, v in node_output.items()},
                iteration=final.get("iteration", 0),
            )

            if node_name == "planner":
                tasks = node_output.get("tasks", [])
                emit("todo_list", {"tasks": tasks})
                emit("status", {"message": f"规划完成：已将主题拆解为 {len(tasks)} 个子任务"})
                await save_tasks(session_id, tasks)

            elif node_name == "executor":
                tasks = node_output.get("tasks", [])
                for task in tasks:
                    task_id = task["id"]
                    status = task["status"]
                    if status in ("in_progress", "completed", "skipped"):
                        emit("task_status", {
                            "task_id": task_id,
                            "status": status,
                            "title": task.get("title", ""),
                            "summary": task.get("summary", ""),
                            "sources": task.get("sources", ""),
                        })
                emit("status", {"message": f"执行完成：{len(tasks)} 个子任务已处理"})
                await save_tasks(session_id, tasks)

            elif node_name == "reporter":
                draft = node_output.get("draft_report", "")
                emit("status", {"message": f"报告初稿已生成（{len(draft)} 字符）"})

            elif node_name == "critic":
                score = node_output.get("critic_score", 0)
                feedback = node_output.get("critic_feedback", "")
                iteration = node_output.get("iteration", 0)
                final_report = node_output.get("final_report", "")

                if final_report:
                    emit("final_report", {"report": final_report})
                    emit("status", {"message": f"终稿通过评审（评分 {score:.1f}/5，{iteration} 轮迭代）"})
                else:
                    emit("critic_result", {
                        "score": score,
                        "feedback": feedback,
                        "iteration": iteration,
                    })
                    emit("status", {"message": f"评审评分 {score:.1f}/5，进入第 {iteration + 1} 轮迭代优化…"})

            # Merge state
            if isinstance(node_output, dict):
                for key, value in node_output.items():
                    if key == "tasks" and isinstance(value, list):
                        final["tasks"] = value
                    elif key == "search_results" and isinstance(value, dict):
                        final["search_results"].update(value)
                    else:
                        final[key] = value  # type: ignore

    except Exception as exc:
        logger.exception("Research streaming failed")
        await update_session(session_id, status="failed", error=str(exc))
        emit("error", {"detail": str(exc)})
        raise

    # Persist final state
    final_report = final.get("final_report") or final.get("draft_report", "")
    tasks = final.get("tasks", [])

    await save_tasks(session_id, tasks)
    await update_session(
        session_id,
        report=final_report,
        critic_score=final.get("critic_score", 0),
        iterations=final.get("iteration", 0),
        status="completed",
    )

    final["session_id"] = session_id
    emit("done", {})
    return dict(final)
