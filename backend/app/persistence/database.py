"""Async PostgreSQL connection pool — with graceful fallback to in-memory storage."""

from __future__ import annotations

import logging
from typing import Any

import asyncpg

from app.config import settings

logger = logging.getLogger(__name__)

_pool: asyncpg.Pool | None = None
_pg_available: bool | None = None
_memory_store: dict[str, Any] = {}  # Fallback in-memory store


async def _ensure_pool() -> asyncpg.Pool | None:
    global _pool, _pg_available
    if _pg_available is False:
        return None

    if _pool is None and _pg_available is None:
        try:
            _pool = await asyncpg.create_pool(
                host=settings.pg_host,
                port=settings.pg_port,
                user=settings.pg_user,
                password=settings.pg_password,
                database=settings.pg_database,
                min_size=1,
                max_size=5,
                timeout=5.0,
            )
            _pg_available = True
            logger.info("Postgres connection pool created")
        except Exception as exc:
            _pg_available = False
            logger.warning("Postgres unavailable, using in-memory fallback: %s", exc)

    return _pool


async def get_pool() -> asyncpg.Pool:
    pool = await _ensure_pool()
    if pool is None:
        raise RuntimeError("Postgres unavailable")
    return pool


async def close_pool() -> None:
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


async def init_schema() -> None:
    """Create tables if they don't exist."""
    pool = await _ensure_pool()
    if pool is None:
        logger.info("Skipping schema init (Postgres unavailable, using in-memory)")
        return

    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS research_sessions (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                topic TEXT NOT NULL,
                report TEXT,
                critic_score REAL DEFAULT 0,
                iterations INT DEFAULT 0,
                status VARCHAR(20) DEFAULT 'running',
                error TEXT,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            );
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS research_tasks (
                id SERIAL PRIMARY KEY,
                session_id UUID NOT NULL REFERENCES research_sessions(id) ON DELETE CASCADE,
                task_index INT NOT NULL,
                title TEXT NOT NULL,
                intent TEXT DEFAULT '',
                query TEXT DEFAULT '',
                status VARCHAR(20) DEFAULT 'pending',
                summary TEXT DEFAULT '',
                sources TEXT DEFAULT '',
                created_at TIMESTAMPTZ DEFAULT NOW()
            );
        """)
    logger.info("Database schema initialized")


async def check_db() -> dict[str, Any]:
    try:
        pool = await _ensure_pool()
        if pool is None:
            return {"status": "fallback", "mode": "memory"}
        async with pool.acquire() as conn:
            row = await conn.fetchrow("SELECT 1 AS ok, NOW() AS ts")
            return {"status": "ok", "time": str(row["ts"])}
    except Exception as exc:
        return {"status": "error", "detail": str(exc)}


def _mem_key(prefix: str, sid: str) -> str:
    return f"{prefix}:{sid}"
