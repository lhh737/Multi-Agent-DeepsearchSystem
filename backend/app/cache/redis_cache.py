"""Redis-based semantic cache — with in-memory fallback when Redis is unavailable."""

from __future__ import annotations

import hashlib
import json
import logging
import time
from typing import Any

import redis.asyncio as aioredis

from app.config import settings

logger = logging.getLogger(__name__)

_redis: aioredis.Redis | None = None
_redis_available: bool | None = None
_mem_cache: dict[str, tuple[float, dict[str, Any]]] = {}  # (expires_at, data)


async def _ensure_redis() -> aioredis.Redis | None:
    global _redis, _redis_available
    if _redis_available is False:
        return None

    if _redis is None and _redis_available is None:
        try:
            _redis = aioredis.Redis(
                host=settings.redis_host, port=settings.redis_port,
                decode_responses=True, socket_connect_timeout=3.0,
            )
            await _redis.ping()
            _redis_available = True
            logger.info("Redis connected on %s:%s", settings.redis_host, settings.redis_port)
        except Exception as exc:
            _redis_available = False
            logger.warning("Redis unavailable, using in-memory cache: %s", exc)

    return _redis


async def close_redis() -> None:
    global _redis
    if _redis:
        await _redis.close()
        _redis = None


def _cache_key(query: str) -> str:
    digest = hashlib.md5(query.strip().lower().encode()).hexdigest()
    return f"search:{digest}"


async def get_cached_search(query: str) -> dict[str, Any] | None:
    r = await _ensure_redis()
    key = _cache_key(query)

    if r:
        try:
            raw = await r.get(key)
            if raw:
                logger.info("Cache HIT (redis): %s", query[:50])
                return json.loads(raw)
        except Exception as exc:
            logger.warning("Redis get failed: %s", exc)
    else:
        # In-memory fallback
        entry = _mem_cache.get(key)
        if entry and entry[0] > time.time():
            logger.info("Cache HIT (memory): %s", query[:50])
            return dict(entry[1])
        elif entry:
            del _mem_cache[key]

    logger.info("Cache MISS: %s", query[:50])
    return None


async def set_cached_search(query: str, result: dict[str, Any]) -> None:
    r = await _ensure_redis()
    key = _cache_key(query)
    data = {
        "results": result.get("results", []),
        "answer": result.get("answer"),
        "backend": result.get("backend", ""),
    }

    if r:
        try:
            await r.setex(key, settings.redis_cache_ttl, json.dumps(data, ensure_ascii=False))
            logger.info("Cached (redis): %s", query[:50])
        except Exception as exc:
            logger.warning("Redis set failed: %s", exc)
    else:
        _mem_cache[key] = (time.time() + settings.redis_cache_ttl, data)
        logger.info("Cached (memory): %s", query[:50])


async def cache_stats() -> dict[str, Any]:
    r = await _ensure_redis()
    if r:
        try:
            info = await r.info("stats")
            return {
                "status": "ok", "backend": "redis",
                "keys": await r.dbsize(),
                "hits": info.get("keyspace_hits", 0),
            }
        except Exception as exc:
            return {"status": "error", "detail": str(exc)}
    else:
        return {"status": "ok", "backend": "memory", "keys": len(_mem_cache)}
