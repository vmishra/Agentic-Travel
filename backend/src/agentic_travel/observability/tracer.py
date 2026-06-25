"""A lightweight, nesting-aware tracer that streams span lifecycle events."""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Literal

from agentic_travel.observability.cost import CostModel, default_cost_model
from agentic_travel.observability.events import SpanEvent
from agentic_travel.observability.span import Span, SpanKind, SpanStatus, TokenUsage

SpanListener = Callable[[SpanEvent], None]

_current_span_id: ContextVar[str | None] = ContextVar("_current_span_id", default=None)


class SpanHandle:
    """Mutable handle to an in-progress span."""

    def __init__(self, span: Span, cost_model: CostModel) -> None:
        """Wrap ``span`` so callers can enrich it while it is open."""
        self._span = span
        self._cost_model = cost_model

    @property
    def span(self) -> Span:
        """The underlying span."""
        return self._span

    def set_attribute(self, key: str, value: str | int | float | bool) -> None:
        """Attach a single attribute to the span."""
        self._span.attributes[key] = value

    def set_usage(self, usage: TokenUsage) -> None:
        """Record token usage and derive cost from the span's model."""
        self._span.usage = usage
        if self._span.model is not None:
            self._span.cost_usd = self._cost_model.estimate(self._span.model, usage)


class Tracer:
    """Creates spans, tracks nesting via contextvars, and emits events."""

    def __init__(
        self,
        cost_model: CostModel | None = None,
        id_factory: Callable[[], str] | None = None,
    ) -> None:
        """Initialize with an optional cost model and id factory (for tests)."""
        self._cost_model = cost_model or default_cost_model()
        self._id_factory = id_factory or (lambda: uuid.uuid4().hex)
        self._trace_id = self._id_factory()
        self._listeners: list[SpanListener] = []
        self._finished: list[Span] = []

    @property
    def trace_id(self) -> str:
        """The id of the trace this tracer is recording."""
        return self._trace_id

    def add_listener(self, listener: SpanListener) -> None:
        """Register a callback to receive span lifecycle events."""
        self._listeners.append(listener)

    def finished_spans(self) -> list[Span]:
        """Return recorded spans in completion order."""
        return list(self._finished)

    def _emit(self, phase: Literal["started", "ended"], span: Span) -> None:
        event = SpanEvent(phase=phase, span=span.model_copy(deep=True))
        for listener in self._listeners:
            listener(event)

    @contextmanager
    def span(
        self,
        name: str,
        kind: SpanKind,
        *,
        model: str | None = None,
        attributes: dict[str, str | int | float | bool] | None = None,
    ) -> Iterator[SpanHandle]:
        """Open a span as the child of the current span, timing its body."""
        span = Span(
            span_id=self._id_factory(),
            trace_id=self._trace_id,
            parent_id=_current_span_id.get(),
            name=name,
            kind=kind,
            started_at=datetime.now(UTC),
            model=model,
            attributes=dict(attributes or {}),
        )
        handle = SpanHandle(span, self._cost_model)
        token = _current_span_id.set(span.span_id)
        start = time.perf_counter()
        self._emit("started", span)
        try:
            yield handle
        except Exception as exc:  # noqa: BLE001 — recorded on the span, then re-raised
            span.status = SpanStatus.ERROR
            span.error_message = str(exc)
            raise
        finally:
            span.duration_ms = round((time.perf_counter() - start) * 1000, 3)
            span.ended_at = datetime.now(UTC)
            _current_span_id.reset(token)
            self._finished.append(span)
            self._emit("ended", span)
