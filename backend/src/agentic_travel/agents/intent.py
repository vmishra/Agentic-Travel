"""Intent classification agent."""

from __future__ import annotations

from pydantic import BaseModel, Field

from agentic_travel.agents.base import Agent
from agentic_travel.agents.models import IntentResult, TripIntent

_SYSTEM = """\
You classify a traveler's message into exactly one intent:
- inquiry: asking about a place, event, or for inspiration.
- itinerary: asking to build or plan a trip.
- post_travel: asking to view or change an existing booking/itinerary.
Also extract a short free-text destination hint if one is mentioned (else null).
Return your best estimate with a calibrated confidence between 0 and 1."""


class IntentOut(BaseModel):
    """Model-facing schema for intent classification."""

    intent: TripIntent
    confidence: float = Field(ge=0.0, le=1.0)
    destination_hint: str | None = None


class IntentAgent(Agent):
    """Classifies a user message into a :class:`TripIntent`."""

    name = "intent"

    def run(self, query: str, *, model: str) -> IntentResult:
        """Classify ``query`` and return the intent with the original text."""
        with self._span():
            parsed, _ = self._llm.generate_structured(
                model=model,
                system=_SYSTEM,
                prompt=query,
                schema=IntentOut,
            )
            return IntentResult(
                intent=parsed.intent,
                confidence=parsed.confidence,
                destination_hint=parsed.destination_hint,
                raw_query=query,
            )
