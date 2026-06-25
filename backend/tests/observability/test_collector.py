from collections.abc import Callable

from agentic_travel.observability.collector import TraceCollector, summarize
from agentic_travel.observability.span import SpanKind, TokenUsage
from agentic_travel.observability.tracer import Tracer


def _ids() -> Callable[[], str]:
    seq = iter(f"id{i}" for i in range(1000))
    return lambda: next(seq)


def test_collector_captures_and_summarizes() -> None:
    tracer = Tracer(id_factory=_ids())
    collector = TraceCollector()
    collector.attach(tracer)
    with tracer.span("root", SpanKind.AGENT):
        with tracer.span("model", SpanKind.MODEL, model="fast") as h:
            h.set_usage(TokenUsage(prompt_tokens=1000, completion_tokens=500))
    summary = collector.summary()
    assert summary.span_count == 2
    assert summary.total_tokens == 1500
    assert summary.by_kind["model"] == 1
    assert summary.by_kind["agent"] == 1
    assert summary.total_cost_usd >= 0


def test_summarize_empty() -> None:
    summary = summarize([])
    assert summary.span_count == 0
    assert summary.total_tokens == 0
