"""FastAPI entry point — LangGraph multi-agent deep research with Postgres + Redis."""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from loguru import logger
from pydantic import BaseModel, Field, field_validator

# --- Suppress noisy third-party logs ---
for _name in ("httpx", "httpcore", "openai._base_client", "tavily", "asyncpg"):
    logging.getLogger(_name).setLevel(logging.WARNING)

from app.config import settings
from app.graph.builder import run_research, run_research_stream
from app.persistence.database import check_db, close_pool, init_schema
from app.persistence.repository import get_session, list_sessions
from app.cache.redis_cache import cache_stats, close_redis, _ensure_redis

# --- Logging ---
logger.remove()
logger.add(
    sys.stderr,
    level=settings.log_level,
    format="<green>{time:HH:mm:ss}</green> | <level>{level: <4}</level> | <level>{message}</level>",
    colorize=True,
)


class ResearchRequest(BaseModel):
    topic: str = Field(..., min_length=2)

    @field_validator("topic")
    @classmethod
    def topic_must_be_meaningful(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 2:
            raise ValueError("研究主题过短，请至少输入 2 个字符")
        return v


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: init DB schema + connect Redis. Shutdown: close all connections."""
    logger.info("Initializing infrastructure...")
    try:
        await init_schema()
        logger.info("Postgres schema ready")
    except Exception as exc:
        logger.warning("Postgres init failed (will retry on use): %s", exc)

    try:
        await _ensure_redis()
        logger.info("Redis connected")
    except Exception as exc:
        logger.warning("Redis init failed (cache disabled): %s", exc)

    logger.info(
        "Deep Research Agent ready | model=%s | search=%s | max_iter=%d | cache_ttl=%ds",
        settings.llm_model_id, settings.search_api,
        settings.max_iterations, settings.redis_cache_ttl,
    )
    yield
    # Shutdown
    await close_pool()
    await close_redis()
    logger.info("Infrastructure shut down")


app = FastAPI(
    title="Deep Research Agent — LangGraph Multi-Agent",
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Health ---
@app.get("/healthz")
async def health_check():
    db_status = await check_db()
    redis_status = await cache_stats()
    return {
        "status": "ok",
        "version": "0.2.0",
        "model": settings.llm_model_id,
        "search": settings.search_api,
        "postgres": db_status,
        "redis": redis_status,
    }


# --- Research endpoints ---
@app.post("/research")
async def research(payload: ResearchRequest):
    """Non-streaming: run full research and return the completed report."""
    try:
        result = await run_research(payload.topic)
    except Exception as exc:
        logger.exception("Research failed")
        raise HTTPException(status_code=500, detail=str(exc))

    return {
        "session_id": result.get("session_id", ""),
        "report": result.get("final_report") or result.get("draft_report", ""),
        "critic_score": result.get("critic_score", 0),
        "iteration": result.get("iteration", 0),
        "tasks": result.get("tasks", []),
    }


@app.post("/research/stream")
async def research_stream(payload: ResearchRequest):
    """SSE streaming: real-time event stream of the research process."""

    async def event_generator():
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=64)

        async def runner():
            try:
                result = await run_research_stream(payload.topic, queue)
                final_report = result.get("final_report") or result.get("draft_report", "")
                if final_report:
                    await queue.put({
                        "type": "final_report",
                        "data": {"report": final_report, "session_id": result.get("session_id", "")},
                    })
            except Exception as exc:
                logger.exception("Streaming research failed")
                await queue.put({"type": "error", "data": {"detail": str(exc)}})
            finally:
                await queue.put({"type": "done", "data": {}})

        task = asyncio.create_task(runner())

        while True:
            event = await queue.get()
            is_done = event.get("type") == "done"
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
            if is_done:
                break

        await task

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# --- Session history ---
@app.get("/sessions")
async def sessions_list(limit: int = 20):
    """List recent research sessions."""
    return {"sessions": await list_sessions(limit)}


@app.get("/sessions/{session_id}")
async def session_detail(session_id: str):
    """Retrieve a specific research session with tasks."""
    session = await get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session
