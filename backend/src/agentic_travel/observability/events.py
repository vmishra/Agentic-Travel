"""Span lifecycle events for streaming to consumers (e.g. the trace view)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from agentic_travel.observability.span import Span


class SpanEvent(BaseModel):
    """Emitted when a span starts or ends."""

    phase: Literal["started", "ended"]
    span: Span
