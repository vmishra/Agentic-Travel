"""Credential-free heuristic strategies for the planning pipeline.

These let the system run end to end with no API key — useful for local demos,
CI, and as a deterministic baseline. `HeuristicLlmClient` covers intent and slot
extraction with simple rules; `HeuristicSynthesizer` schedules the itinerary
directly from the planning context. Swap in `GeminiClient` /
`LlmSynthesizer` for production-quality reasoning.
"""

from __future__ import annotations

import re
from datetime import date, time, timedelta
from typing import TYPE_CHECKING, TypeVar, cast

from pydantic import BaseModel

from agentic_travel.agents.intent import IntentOut
from agentic_travel.agents.models import BriefExtract, TripIntent
from agentic_travel.agents.synthesizer import (
    HotelChoice,
    PlannedActivity,
    PlannedDay,
    SynthesisPlan,
)
from agentic_travel.graph.models import OpeningHours
from agentic_travel.graph.store import GraphStore
from agentic_travel.llm.client import LlmClient, LlmResult
from agentic_travel.observability.span import TokenUsage

if TYPE_CHECKING:
    from agentic_travel.agents.planning import PlanningContext
    from agentic_travel.graph.models import POI

T = TypeVar("T", bound=BaseModel)

_POST_TRAVEL = ("my booking", "my trip", "existing", "change my", "reschedule", "cancel my")
_ITINERARY = ("plan", "itinerary", "trip", "days", "nights", "holiday", "vacation", "visit")
_INTERESTS = (
    "beaches",
    "beach",
    "history",
    "food",
    "nightlife",
    "nature",
    "shopping",
    "adventure",
    "wellness",
)
_DAY_SLOTS: tuple[tuple[time, time], ...] = (
    (time(9, 30), time(11, 0)),
    (time(11, 30), time(13, 0)),
    (time(14, 0), time(16, 0)),
)


class HeuristicLlmClient(LlmClient):
    """Rule-based stand-in for the model covering intent and slot extraction."""

    def generate(
        self,
        *,
        model: str,
        prompt: str,
        system: str | None = None,
        temperature: float | None = None,
    ) -> LlmResult:
        """Return a minimal canned text result (offline mode)."""
        return LlmResult(
            text="",
            model=model,
            usage=TokenUsage(prompt_tokens=0, completion_tokens=0),
        )

    def generate_structured(
        self,
        *,
        model: str,
        prompt: str,
        schema: type[T],
        system: str | None = None,
        temperature: float | None = None,
    ) -> tuple[T, LlmResult]:
        """Produce an IntentOut or BriefExtract from simple rules over the prompt."""
        result = LlmResult(
            text="", model=model, usage=TokenUsage(prompt_tokens=0, completion_tokens=0)
        )
        if schema is IntentOut:
            return cast("T", self._intent(prompt)), result
        if schema is BriefExtract:
            return cast("T", self._brief(prompt)), result
        raise TypeError(f"HeuristicLlmClient does not support schema {schema.__name__}")

    @staticmethod
    def _intent(prompt: str) -> IntentOut:
        text = prompt.lower()
        if any(token in text for token in _POST_TRAVEL):
            intent = TripIntent.POST_TRAVEL
        elif any(token in text for token in _ITINERARY):
            intent = TripIntent.ITINERARY
        else:
            intent = TripIntent.INQUIRY
        return IntentOut(intent=intent, confidence=0.6)

    @staticmethod
    def _brief(prompt: str) -> BriefExtract:
        text = prompt.lower()
        nights = _extract_nights(text)
        party = _extract_party(text)
        occasion = next(
            (o for o in ("anniversary", "honeymoon", "birthday", "wedding") if o in text), None
        )
        interests = list(dict.fromkeys(w for w in _INTERESTS if w in text))
        return BriefExtract(
            destination_query=prompt,
            nights=nights,
            party_size=party,
            occasion=occasion,
            interests=interests,
        )


def _extract_nights(text: str) -> int | None:
    match = re.search(r"(\d+)\s*nights?", text)
    if match:
        return int(match.group(1))
    match = re.search(r"(\d+)\s*days?", text)
    if match:
        return max(1, int(match.group(1)) - 1)
    return None


def _extract_party(text: str) -> int | None:
    match = re.search(r"(\d+)\s*(?:people|persons|adults|travellers|travelers|pax)", text)
    if match:
        return int(match.group(1))
    if any(w in text for w in ("couple", "honeymoon", "anniversary")):
        return 2
    if "family" in text:
        return 4
    return None


def _slot_fits(hours: OpeningHours | None, weekday: int, start: time, end: time) -> bool:
    if hours is None:
        return True
    if weekday not in hours.days:
        return False
    opens_h, opens_m = (int(p) for p in hours.opens.split(":"))
    closes_h, closes_m = (int(p) for p in hours.closes.split(":"))
    opens = opens_h * 60 + opens_m
    closes = closes_h * 60 + closes_m
    return start.hour * 60 + start.minute >= opens and end.hour * 60 + end.minute <= closes


class HeuristicSynthesizer:
    """Deterministic synthesis strategy that schedules directly from context."""

    def __init__(self, store: GraphStore) -> None:
        """Store the graph for opening-hours-aware scheduling."""
        self._store = store

    def propose(
        self, context: PlanningContext, *, feedback: list[str] | None = None
    ) -> SynthesisPlan:
        """Pick the cheapest flights, top hotel per city, and schedule POIs."""
        outbound = context.outbound_flights[0].offer_id if context.outbound_flights else None
        inbound = context.return_flights[0].offer_id if context.return_flights else None
        hotels = [
            HotelChoice(city_id=city.city_id, hotel_offer_id=city.hotels[0].offer_id)
            for city in context.cities
            if city.hotels
        ]
        days = self._schedule(context)
        names = ", ".join(city.city_name for city in context.cities) or "your destination"
        return SynthesisPlan(
            title=f"{len(days)}-day trip to {names}",
            summary=f"A curated plan covering {names}.",
            outbound_flight_id=outbound,
            return_flight_id=inbound,
            hotels=hotels,
            days=days,
        )

    def _schedule(self, context: PlanningContext) -> list[PlannedDay]:
        base = context.brief.start_date or date(2026, 1, 1)
        days: list[PlannedDay] = []
        day_index = 1
        for city in context.cities:
            remaining: list[POI] = list(city.candidate_pois)
            for _ in range(max(1, city.nights)):
                when = base + timedelta(days=day_index - 1)
                activities = self._fill_day(remaining, when.weekday())
                days.append(
                    PlannedDay(
                        day_index=day_index,
                        date=when,
                        city_id=city.city_id,
                        activities=activities,
                    )
                )
                day_index += 1
        return days

    @staticmethod
    def _fill_day(remaining: list[POI], weekday: int) -> list[PlannedActivity]:
        activities: list[PlannedActivity] = []
        for start, end in _DAY_SLOTS:
            chosen = next(
                (p for p in remaining if _slot_fits(p.opening_hours, weekday, start, end)), None
            )
            if chosen is None:
                continue
            remaining.remove(chosen)
            activities.append(PlannedActivity(poi_id=chosen.id, start=start, end=end))
        return activities
