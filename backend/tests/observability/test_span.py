from datetime import UTC, datetime

from agentic_travel.observability.span import (
    Span,
    SpanKind,
    SpanStatus,
    TokenUsage,
)


def test_token_usage_total() -> None:
    usage = TokenUsage(prompt_tokens=120, completion_tokens=80)
    assert usage.total_tokens == 200


def test_open_span_then_closed() -> None:
    span = Span(
        span_id="s1",
        trace_id="t1",
        parent_id=None,
        name="intent",
        kind=SpanKind.AGENT,
        started_at=datetime(2026, 6, 26, tzinfo=UTC),
        attributes={"intent": "itinerary"},
    )
    assert span.is_open is True
    assert span.status is SpanStatus.OK
    assert span.attributes["intent"] == "itinerary"
