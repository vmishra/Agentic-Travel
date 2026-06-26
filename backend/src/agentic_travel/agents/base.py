"""Shared base for planning agents."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from agentic_travel.llm.client import LlmClient
from agentic_travel.observability.span import SpanKind
from agentic_travel.observability.tracer import SpanHandle, Tracer


class Agent:
    """Base class wiring an agent to a model client and the tracer.

    Subclasses set ``name`` and implement their own ``run`` method, wrapping the
    body in :meth:`_span` so the step appears in the trace.
    """

    name: str = "agent"

    def __init__(self, llm: LlmClient, *, tracer: Tracer | None = None) -> None:
        """Store the model client and optional tracer."""
        self._llm = llm
        self._tracer = tracer

    @contextmanager
    def _span(self) -> Iterator[SpanHandle | None]:
        """Open an AGENT span for this agent if a tracer is configured."""
        if self._tracer is None:
            yield None
        else:
            with self._tracer.span(self.name, SpanKind.AGENT) as handle:
                yield handle
