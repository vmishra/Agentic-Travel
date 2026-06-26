from typing import Any

from pydantic import BaseModel

from agentic_travel.llm.client import FakeLlmClient, GeminiClient, LlmResult
from agentic_travel.observability.span import SpanKind, TokenUsage
from agentic_travel.observability.tracer import Tracer


class _Intent(BaseModel):
    intent: str
    confidence: float


# --- FakeLlmClient -----------------------------------------------------------


def test_fake_generate_returns_scripted_text() -> None:
    fake = FakeLlmClient(texts=["hello world"])
    result = fake.generate(model="fast", prompt="hi", system="be nice")
    assert result.text == "hello world"
    assert result.model == "fast"
    assert result.usage.total_tokens > 0
    assert fake.calls[0]["prompt"] == "hi"


def test_fake_generate_structured_returns_object() -> None:
    obj = _Intent(intent="itinerary", confidence=0.9)
    fake = FakeLlmClient(objects=[obj])
    value, result = fake.generate_structured(model="fast", prompt="x", schema=_Intent)
    assert value == obj
    assert isinstance(result, LlmResult)


# --- GeminiClient (stubbed transport) ----------------------------------------


class _StubUsage:
    def __init__(self, prompt: int, candidates: int) -> None:
        self.prompt_token_count = prompt
        self.candidates_token_count = candidates


class _StubResponse:
    def __init__(self, text: str, usage: _StubUsage, parsed: Any = None) -> None:
        self.text = text
        self.usage_metadata = usage
        self.parsed = parsed


class _StubModels:
    def __init__(self, response: _StubResponse) -> None:
        self._response = response
        self.calls: list[dict[str, Any]] = []

    def generate_content(self, **kwargs: Any) -> _StubResponse:
        self.calls.append(kwargs)
        return self._response


class _StubGenAiClient:
    def __init__(self, response: _StubResponse) -> None:
        self.models = _StubModels(response)


def test_gemini_generate_parses_text_and_usage() -> None:
    stub = _StubGenAiClient(_StubResponse("planned!", _StubUsage(100, 40)))
    client = GeminiClient(stub)
    result = client.generate(model="planner", prompt="plan a trip", system="be concise")
    assert result.text == "planned!"
    assert result.usage == TokenUsage(prompt_tokens=100, completion_tokens=40)
    assert stub.models.calls[0]["model"] == "planner"


def test_gemini_generate_emits_traced_span_with_cost() -> None:
    stub = _StubGenAiClient(_StubResponse("ok", _StubUsage(1_000_000, 0)))
    tracer = Tracer()
    client = GeminiClient(stub, tracer=tracer)
    client.generate(model="fast", prompt="hi")
    span = tracer.finished_spans()[0]
    assert span.kind is SpanKind.MODEL
    assert span.model == "fast"
    assert span.usage is not None
    assert span.cost_usd is not None and span.cost_usd > 0


def test_gemini_generate_structured_returns_parsed() -> None:
    parsed = _Intent(intent="inquiry", confidence=0.7)
    response = _StubResponse('{"intent":"inquiry","confidence":0.7}', _StubUsage(10, 5), parsed)
    client = GeminiClient(_StubGenAiClient(response))
    value, result = client.generate_structured(model="fast", prompt="classify", schema=_Intent)
    assert value == parsed
    assert result.usage.prompt_tokens == 10
