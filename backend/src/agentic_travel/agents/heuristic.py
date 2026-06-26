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

from dateutil import parser as date_parser
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
_DAY_START_MIN = 9 * 60 + 30  # first activity starts 09:30
_DAY_LAST_END_MIN = 22 * 60  # nothing scheduled to end after 22:00
_VISIT_MIN = 90
_GAP_MIN = 30
_MAX_ACTIVITIES_PER_DAY = 4


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
        start, range_nights = _extract_dates(prompt)
        nights = range_nights if range_nights is not None else _extract_nights(text)
        # If a duration is given without an explicit date, assume a near-future
        # start so flights can be priced. Live reasoning extracts real dates.
        if start is None and nights is not None:
            start = date.today() + timedelta(days=30)
        party = _extract_party(text)
        occasion = next(
            (o for o in ("anniversary", "honeymoon", "birthday", "wedding") if o in text), None
        )
        interests = list(dict.fromkeys(w for w in _INTERESTS if w in text))
        return BriefExtract(
            destination_query=prompt,
            start_date=start,
            nights=nights,
            party_size=party,
            occasion=occasion,
            interests=interests,
        )


_MONTH = r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*"
_DATE_PHRASE = re.compile(
    r"\b("
    r"\d{4}-\d{1,2}-\d{1,2}"  # 2026-06-27
    r"|\d{1,2}[/-]\d{1,2}[/-]\d{2,4}"  # 27/06/2026
    rf"|\d{{1,2}}(?:st|nd|rd|th)?\s+{_MONTH}(?:\s+\d{{4}})?"  # 27th June 2026
    rf"|{_MONTH}\s+\d{{1,2}}(?:st|nd|rd|th)?(?:,?\s+\d{{4}})?"  # June 27, 2026
    r")\b",
    re.IGNORECASE,
)


def _extract_dates(text: str) -> tuple[date | None, int | None]:
    """Find date phrases; return (start_date, nights) where nights spans a range."""
    found: list[date] = []
    for match in _DATE_PHRASE.finditer(text):
        # Strip ordinal suffixes that follow a number (27th -> 27) without
        # touching month names like "August".
        cleaned = re.sub(r"(\d{1,2})(?:st|nd|rd|th)", r"\1", match.group(0), flags=re.IGNORECASE)
        try:
            found.append(date_parser.parse(cleaned, fuzzy=True).date())
        except (ValueError, OverflowError):
            continue
    if not found:
        return None, None
    found.sort()
    start = found[0]
    if len(found) >= 2 and found[-1] > start:
        return start, (found[-1] - start).days
    return start, None


def _extract_nights(text: str) -> int | None:
    """Return trip length in itinerary-days from a "N nights/days" phrase."""
    match = re.search(r"(\d+)\s*(?:nights?|nts?|days?|dys?)", text)
    if match:
        return max(1, int(match.group(1)))
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


def _hhmm_to_min(value: str) -> int:
    hours, minutes = value.split(":")
    return int(hours) * 60 + int(minutes)


def _open_window(hours: OpeningHours | None, weekday: int) -> tuple[int, int] | None:
    """Return (opens, closes) in minutes for the weekday, or None if closed."""
    if hours is None:
        return 0, 24 * 60
    if weekday not in hours.days:
        return None
    opens = _hhmm_to_min(hours.opens)
    closes = _hhmm_to_min(hours.closes)
    if closes <= opens:  # "00:00"/overnight close means end of day
        closes = 24 * 60
    return opens, closes


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
            city_days = max(1, city.nights)
            for offset in range(city_days):
                days_left = city_days - offset
                # Recompute each day so points of interest spread across every
                # day rather than front-loading and leaving later days empty.
                target = min(
                    _MAX_ACTIVITIES_PER_DAY,
                    max(1, -(-len(remaining) // days_left)) if remaining else 0,
                )
                when = base + timedelta(days=day_index - 1)
                activities = self._fill_day(remaining, when.weekday(), target)
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
    def _fill_day(remaining: list[POI], weekday: int, target: int) -> list[PlannedActivity]:
        """Schedule up to ``target`` POIs within their opening hours, in order."""
        open_today = [
            (poi, window)
            for poi in remaining
            if (window := _open_window(poi.opening_hours, weekday)) is not None
        ]
        # Earliest-opening first so the day flows morning to evening.
        open_today.sort(key=lambda item: (item[1][0], -item[0].rating))

        activities: list[PlannedActivity] = []
        clock = _DAY_START_MIN
        for poi, (opens, closes) in open_today:
            if len(activities) >= target:
                break
            start = max(clock, opens)
            end = min(start + _VISIT_MIN, closes)
            if start >= _DAY_LAST_END_MIN or end - start < 45:
                continue
            activities.append(
                PlannedActivity(
                    poi_id=poi.id,
                    start=time(start // 60, start % 60),
                    end=time(min(end, _DAY_LAST_END_MIN) // 60, min(end, _DAY_LAST_END_MIN) % 60),
                )
            )
            remaining.remove(poi)
            clock = end + _GAP_MIN
        # Never leave a day empty while POIs remain: place the best one we can.
        if not activities and remaining:
            poi = next((p for p, _ in open_today), remaining[0])
            remaining.remove(poi)
            fallback_end = _DAY_START_MIN + _VISIT_MIN
            activities.append(
                PlannedActivity(
                    poi_id=poi.id,
                    start=time(_DAY_START_MIN // 60, _DAY_START_MIN % 60),
                    end=time(fallback_end // 60, fallback_end % 60),
                )
            )
        return activities
