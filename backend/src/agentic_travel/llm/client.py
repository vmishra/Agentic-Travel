"""LLM client abstraction over Gemini, with a deterministic fake for testing.

`LlmClient` is the seam the agent layer depends on. `GeminiClient` is the real
implementation backed by the ``google-genai`` SDK and instrumented with the
tracer (every call becomes a metered MODEL span). `FakeLlmClient` returns
scripted responses so the whole agent system is unit-testable without network.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, TypeVar

from pydantic import BaseModel

from agentic_travel.config.settings import MissingConfigError, Settings
from agentic_travel.observability.span import SpanKind, TokenUsage
from agentic_travel.observability.tracer import Tracer

if TYPE_CHECKING:
    from collections.abc import Callable

T = TypeVar("T", bound=BaseModel)


class LlmResult(BaseModel):
    """The text and token accounting of a single model call."""

    text: str
    model: str
    usage: TokenUsage


class LlmClient(ABC):
    """Interface the agent layer uses to call a language model."""

    @abstractmethod
    def generate(
        self,
        *,
        model: str,
        prompt: str,
        system: str | None = None,
        temperature: float | None = None,
    ) -> LlmResult:
        """Generate free-form text for a prompt."""

    @abstractmethod
    def generate_structured(
        self,
        *,
        model: str,
        prompt: str,
        schema: type[T],
        system: str | None = None,
        temperature: float | None = None,
    ) -> tuple[T, LlmResult]:
        """Generate a response constrained to ``schema`` and return the parsed value."""


def _estimate_tokens(text: str) -> int:
    """Roughly approximate token count from character length (~4 chars/token)."""
    return max(1, len(text) // 4)


class FakeLlmClient(LlmClient):
    """An ``LlmClient`` that returns scripted responses and records calls."""

    def __init__(
        self,
        *,
        texts: list[str] | None = None,
        objects: list[BaseModel] | None = None,
    ) -> None:
        """Seed the client with scripted text and/or structured responses."""
        self._texts = list(texts or [])
        self._objects = list(objects or [])
        self.calls: list[dict[str, Any]] = []

    def generate(
        self,
        *,
        model: str,
        prompt: str,
        system: str | None = None,
        temperature: float | None = None,
    ) -> LlmResult:
        """Return the next scripted text response."""
        self.calls.append({"model": model, "prompt": prompt, "system": system})
        text = self._texts.pop(0) if self._texts else ""
        usage = TokenUsage(
            prompt_tokens=_estimate_tokens((system or "") + prompt),
            completion_tokens=_estimate_tokens(text),
        )
        return LlmResult(text=text, model=model, usage=usage)

    def generate_structured(
        self,
        *,
        model: str,
        prompt: str,
        schema: type[T],
        system: str | None = None,
        temperature: float | None = None,
    ) -> tuple[T, LlmResult]:
        """Return the next scripted structured response."""
        self.calls.append(
            {"model": model, "prompt": prompt, "system": system, "schema": schema.__name__}
        )
        if not self._objects:
            raise IndexError("FakeLlmClient has no scripted structured responses left")
        obj = self._objects.pop(0)
        if not isinstance(obj, schema):
            raise TypeError(
                f"scripted object {type(obj).__name__} does not match expected {schema.__name__}"
            )
        text = obj.model_dump_json()
        usage = TokenUsage(
            prompt_tokens=_estimate_tokens((system or "") + prompt),
            completion_tokens=_estimate_tokens(text),
        )
        return obj, LlmResult(text=text, model=model, usage=usage)


def _usage_from(response: Any) -> TokenUsage:
    meta = response.usage_metadata
    return TokenUsage(
        prompt_tokens=meta.prompt_token_count or 0,
        completion_tokens=meta.candidates_token_count or 0,
    )


class GeminiClient(LlmClient):
    """An ``LlmClient`` backed by the google-genai SDK, traced per call."""

    def __init__(self, client: Any, tracer: Tracer | None = None) -> None:
        """Wrap an initialized google-genai client; ``tracer`` enables metering."""
        self._client = client
        self._tracer = tracer

    @classmethod
    def from_settings(cls, settings: Settings, tracer: Tracer | None = None) -> GeminiClient:
        """Construct a client from settings (Gemini Developer API or Vertex AI)."""
        from google import genai

        if settings.google_genai_use_vertexai:
            client = genai.Client(
                vertexai=True,
                project=settings.google_cloud_project,
                location=settings.google_cloud_location,
            )
        else:
            if not settings.gemini_api_key:
                raise MissingConfigError("GEMINI_API_KEY is required for live model calls")
            client = genai.Client(api_key=settings.gemini_api_key)
        return cls(client, tracer)

    def _invoke(self, model: str, run: Callable[[], Any]) -> Any:
        if self._tracer is None:
            return run()
        with self._tracer.span(f"gemini:{model}", SpanKind.MODEL, model=model) as handle:
            response = run()
            handle.set_usage(_usage_from(response))
            return response

    def generate(
        self,
        *,
        model: str,
        prompt: str,
        system: str | None = None,
        temperature: float | None = None,
    ) -> LlmResult:
        """Call Gemini for free-form text."""
        from google.genai import types

        config = types.GenerateContentConfig(
            system_instruction=system, temperature=temperature
        )
        response = self._invoke(
            model,
            lambda: self._client.models.generate_content(
                model=model, contents=prompt, config=config
            ),
        )
        return LlmResult(text=response.text or "", model=model, usage=_usage_from(response))

    def generate_structured(
        self,
        *,
        model: str,
        prompt: str,
        schema: type[T],
        system: str | None = None,
        temperature: float | None = None,
    ) -> tuple[T, LlmResult]:
        """Call Gemini with a JSON schema constraint and return the parsed value."""
        from google.genai import types

        config = types.GenerateContentConfig(
            system_instruction=system,
            temperature=temperature,
            response_mime_type="application/json",
            response_schema=schema,
        )
        response = self._invoke(
            model,
            lambda: self._client.models.generate_content(
                model=model, contents=prompt, config=config
            ),
        )
        parsed = response.parsed
        value = parsed if isinstance(parsed, schema) else schema.model_validate_json(response.text)
        return value, LlmResult(text=response.text or "", model=model, usage=_usage_from(response))
