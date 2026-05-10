"""LangSmith tracing setup for full observability of the multi-agent pipeline."""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from app.config import settings

logger = logging.getLogger(__name__)


def setup_langsmith() -> None:
    """Configure LangSmith environment variables for auto-tracing."""
    if not settings.langsmith_api_key:
        logger.info("LangSmith tracing disabled (no API key)")
        return

    os.environ.setdefault("LANGSMITH_TRACING", "true")
    os.environ.setdefault("LANGSMITH_API_KEY", settings.langsmith_api_key)
    os.environ.setdefault("LANGSMITH_PROJECT", settings.langsmith_project)
    os.environ.setdefault("LANGSMITH_ENDPOINT", "https://api.smith.langchain.com")

    logger.info(
        "LangSmith tracing enabled | project=%s",
        settings.langsmith_project,
    )


def trace_llm_call(
    agent_name: str,
    messages: list[dict[str, Any]],
    response: str,
    *,
    model: str | None = None,
    duration_ms: float | None = None,
) -> None:
    """Record an LLM call to LangSmith using the SDK (fallback if env vars not set)."""
    if not settings.langsmith_enabled:
        return

    try:
        from langsmith import traceable

        # This decorator approach only works when applied at import time.
        # For dynamic tracing, we use the low-level client.
        from langsmith import Client

        client = Client()
        client.create_run(
            name=f"{agent_name}_llm_call",
            run_type="llm",
            inputs={"messages": messages},
            outputs={"content": response[:2000]},
            extra={
                "model": model or settings.llm_model_id,
                "duration_ms": duration_ms,
                "agent": agent_name,
            },
        )
    except Exception as exc:
        logger.debug("LangSmith trace skipped: %s", exc)


def trace_agent_step(
    node_name: str,
    inputs: dict[str, Any],
    outputs: dict[str, Any],
    *,
    iteration: int = 0,
) -> None:
    """Record an agent node execution to LangSmith."""
    if not settings.langsmith_enabled:
        return

    try:
        from langsmith import Client

        client = Client()
        client.create_run(
            name=f"node_{node_name}",
            run_type="chain",
            inputs=inputs,
            outputs=outputs,
            extra={
                "node": node_name,
                "iteration": iteration,
            },
        )
    except Exception as exc:
        logger.debug("LangSmith trace skipped: %s", exc)
