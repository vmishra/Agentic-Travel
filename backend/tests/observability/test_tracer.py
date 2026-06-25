from collections.abc import Callable

import pytest

from agentic_travel.observability.events import SpanEvent
from agentic_travel.observability.span import SpanKind, TokenUsage
from agentic_travel.observability.tracer import Tracer


def _counter_ids() -> Callable[[], str]:
    seq = iter(f"id{i}" for i in range(1000))
    return lambda: next(seq)


def test_nested_spans_link_parent_child() -> None:
    tracer = Tracer(id_factory=_counter_ids())
    with tracer.span("root", SpanKind.AGENT):
        with tracer.span("child", SpanKind.TOOL):
            pass
    spans = {s.name: s for s in tracer.finished_spans()}
    assert spans["child"].parent_id == spans["root"].span_id
    assert spans["root"].parent_id is None
    assert spans["child"].duration_ms is not None and spans["child"].duration_ms >= 0


def test_events_emitted_for_start_and_end() -> None:
    tracer = Tracer(id_factory=_counter_ids())
    events: list[SpanEvent] = []
    tracer.add_listener(events.append)
    with tracer.span("op", SpanKind.INTERNAL):
        pass
    phases = [e.phase for e in events]
    assert phases == ["started", "ended"]


def test_usage_sets_cost() -> None:
    tracer = Tracer(id_factory=_counter_ids())
    with tracer.span("call", SpanKind.MODEL, model="fast") as handle:
        handle.set_usage(TokenUsage(prompt_tokens=1_000_000, completion_tokens=0))
    span = tracer.finished_spans()[0]
    assert span.usage is not None
    assert span.cost_usd is not None and span.cost_usd > 0


def test_error_status_recorded() -> None:
    tracer = Tracer(id_factory=_counter_ids())
    with pytest.raises(ValueError):  # noqa: PT012
        with tracer.span("boom", SpanKind.INTERNAL):
            raise ValueError("fail")
    span = tracer.finished_spans()[0]
    assert span.status.value == "error"
    assert span.error_message == "fail"
