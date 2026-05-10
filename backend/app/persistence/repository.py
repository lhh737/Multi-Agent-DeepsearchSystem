"""Repository layer — Postgres with automatic in-memory fallback."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from app.persistence.database import _ensure_pool, _mem_key, _memory_store

logger = logging.getLogger(__name__)


async def create_session(topic: str) -> str:
    """Create a new research session and return its UUID."""
    session_id = str(uuid.uuid4())
    pool = await _ensure_pool()

    if pool:
        async with pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO research_sessions (id, topic, status) VALUES ($1, $2, 'running')",
                session_id, topic,
            )
    else:
        _memory_store[_mem_key("session", session_id)] = {
            "id": session_id, "topic": topic, "report": None,
            "critic_score": 0, "iterations": 0, "status": "running",
            "error": None, "created_at": datetime.now(timezone.utc).isoformat(),
            "tasks": [],
        }

    logger.info("Created session %s (pg=%s)", session_id[:8], bool(pool))
    return session_id


async def update_session(
    session_id: str, *, report: str | None = None,
    critic_score: float | None = None, iterations: int | None = None,
    status: str | None = None, error: str | None = None,
) -> None:
    pool = await _ensure_pool()
    if pool:
        async with pool.acquire() as conn:
            parts = []; args = []; idx = 1
            for val, col in [(report, "report"), (critic_score, "critic_score"),
                             (iterations, "iterations"), (status, "status"), (error, "error")]:
                if val is not None:
                    parts.append(f"{col} = ${idx}"); args.append(val); idx += 1
            if parts:
                parts.append("updated_at = NOW()"); args.append(session_id)
                await conn.execute(
                    f"UPDATE research_sessions SET {', '.join(parts)} WHERE id = ${idx}", *args,
                )
    else:
        key = _mem_key("session", session_id)
        if key in _memory_store:
            s = _memory_store[key]
            if report is not None: s["report"] = report
            if critic_score is not None: s["critic_score"] = critic_score
            if iterations is not None: s["iterations"] = iterations
            if status is not None: s["status"] = status
            if error is not None: s["error"] = error


async def save_tasks(session_id: str, tasks: list[dict[str, Any]]) -> None:
    pool = await _ensure_pool()
    if pool:
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM research_tasks WHERE session_id = $1", session_id)
            for task in tasks:
                sources = task.get("sources", "")
                if isinstance(sources, (list, dict)):
                    sources = json.dumps(sources, ensure_ascii=False)
                await conn.execute(
                    """INSERT INTO research_tasks
                       (session_id, task_index, title, intent, query, status, summary, sources)
                       VALUES ($1, $2, $3, $4, $5, $6, $7, $8)""",
                    session_id, task.get("id", 0), task.get("title", ""),
                    task.get("intent", ""), task.get("query", ""),
                    task.get("status", "pending"), task.get("summary", ""), sources,
                )
    else:
        key = _mem_key("session", session_id)
        if key in _memory_store:
            _memory_store[key]["tasks"] = tasks


async def get_session(session_id: str) -> dict[str, Any] | None:
    pool = await _ensure_pool()
    if pool:
        async with pool.acquire() as conn:
            session = await conn.fetchrow("SELECT * FROM research_sessions WHERE id = $1", session_id)
            if not session: return None
            tasks = await conn.fetch(
                "SELECT * FROM research_tasks WHERE session_id = $1 ORDER BY task_index", session_id,
            )
            return {
                "id": str(session["id"]), "topic": session["topic"],
                "report": session["report"], "critic_score": session["critic_score"],
                "iterations": session["iterations"], "status": session["status"],
                "error": session["error"], "created_at": str(session["created_at"]),
                "tasks": [
                    {"id": t["task_index"], "title": t["title"], "intent": t["intent"],
                     "query": t["query"], "status": t["status"], "summary": t["summary"],
                     "sources": t["sources"]}
                    for t in tasks
                ],
            }
    else:
        key = _mem_key("session", session_id)
        return _memory_store.get(key)


async def list_sessions(limit: int = 20) -> list[dict[str, Any]]:
    pool = await _ensure_pool()
    if pool:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT id, topic, critic_score, status, created_at "
                "FROM research_sessions ORDER BY created_at DESC LIMIT $1", limit,
            )
            return [
                {"id": str(r["id"]), "topic": r["topic"],
                 "critic_score": r["critic_score"], "status": r["status"],
                 "created_at": str(r["created_at"])}
                for r in rows
            ]
    else:
        return sorted(
            [{"id": v["id"], "topic": v["topic"], "critic_score": v["critic_score"],
              "status": v["status"], "created_at": v["created_at"]}
             for v in _memory_store.values() if isinstance(v, dict) and "topic" in v],
            key=lambda x: x["created_at"], reverse=True,
        )[:limit]
