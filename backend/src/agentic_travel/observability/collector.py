"""Collect finished spans from a tracer and summarize a trace."""

from __future__ import annotations

from collections import Counter
from decimal import Decimal

from pydantic import BaseModel, Field

from agentic_travel.observability.events import SpanEvent
from agentic_travel.observability.span import Span
from agentic_travel.observability.tracer import Tracer


class TraceSummary(BaseModel):
    """Aggregate metrics over the spans of a single trace."""

    trace_id: str
    span_count: int
    total_duration_ms: float
    total_cost_usd: Decimal
    total_tokens: int
    by_kind: dict[str, int] = Field(default_factory=dict)


def summarize(spans: list[Span]) -> TraceSummary:
    """Compute aggregate metrics for a list of spans."""
    if not spans:
        return TraceSummary(
            trace_id="",
            span_count=0,
            total_duration_ms=0.0,
            total_cost_usd=Decimal("0"),
            total_tokens=0,
            by_kind={},
        )
    total_cost = sum((s.cost_usd or Decimal("0") for s in spans), Decimal("0"))
    total_tokens = sum(s.usage.total_tokens for s in spans if s.usage is not None)
    by_kind = Counter(s.kind.value for s in spans)
    roots = [s for s in spans if s.parent_id is None]
    total_duration = max((s.duration_ms or 0.0 for s in roots), default=0.0)
    return TraceSummary(
        trace_id=spans[0].trace_id,
        span_count=len(spans),
        total_duration_ms=total_duration,
        total_cost_usd=total_cost,
        total_tokens=total_tokens,
        by_kind=dict(by_kind),
    )


class TraceCollector:
    """Stores ended spans emitted by a tracer for later inspection/replay."""

    def __init__(self) -> None:
        """Start with an empty span buffer."""
        self._spans: list[Span] = []

    def attach(self, tracer: Tracer) -> None:
        """Subscribe to a tracer's ended-span events."""
        tracer.add_listener(self._on_event)

    def _on_event(self, event: SpanEvent) -> None:
        if event.phase == "ended":
            self._spans.append(event.span)

    def spans(self) -> list[Span]:
        """Return all captured (ended) spans."""
        return list(self._spans)

    def summary(self) -> TraceSummary:
        """Summarize the captured spans."""
        return summarize(self._spans)
