"""Shared data models for API and internal state."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, Field, field_validator


class ResearchRequest(BaseModel):
    """Payload for triggering a research run."""

    topic: str = Field(..., min_length=2, description="Research topic")
    search_api: str | None = Field(default=None, description="Override search backend")

    @field_validator("topic")
    @classmethod
    def topic_must_be_meaningful(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 2:
            raise ValueError("研究主题过短，请至少输入 2 个字符")
        return v


@dataclass
class SubTask:
    """A single sub-task within the research plan."""

    id: int
    title: str
    intent: str
    query: str
    status: str = "pending"  # pending | in_progress | completed | skipped
    summary: str = ""
    sources: list[dict[str, str]] = field(default_factory=list)


class SSEEvent(BaseModel):
    """An event pushed to the frontend via SSE."""

    type: str
    data: dict[str, Any] = Field(default_factory=dict)
