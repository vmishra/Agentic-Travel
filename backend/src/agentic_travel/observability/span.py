"""Span model: one timed, attributed unit of work in a trace."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field


class SpanKind(StrEnum):
    """The kind of work a span represents."""

    AGENT = "agent"
    TOOL = "tool"
    MODEL = "model"
    MCP = "mcp"
    INTERNAL = "internal"


class SpanStatus(StrEnum):
    """Terminal status of a span."""

    OK = "ok"
    ERROR = "error"


class TokenUsage(BaseModel):
    """Token counts for a model call."""

    prompt_tokens: int = Field(ge=0)
    completion_tokens: int = Field(ge=0)

    @property
    def total_tokens(self) -> int:
        """Sum of prompt and completion tokens."""
        return self.prompt_tokens + self.completion_tokens


class Span(BaseModel):
    """A single timed operation, optionally nested under a parent span."""

    span_id: str
    trace_id: str
    parent_id: str | None
    name: str
    kind: SpanKind
    status: SpanStatus = SpanStatus.OK
    started_at: datetime
    ended_at: datetime | None = None
    duration_ms: float | None = None
    attributes: dict[str, str | int | float | bool] = Field(default_factory=dict)
    model: str | None = None
    usage: TokenUsage | None = None
    cost_usd: Decimal | None = None
    error_message: str | None = None

    @property
    def is_open(self) -> bool:
        """True while the span has not been closed."""
        return self.ended_at is None
