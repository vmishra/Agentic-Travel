"""Itinerary synthesis: the model proposes a plan, code assembles it.

The model emits a light :class:`SynthesisPlan` referencing offers and POIs by
id plus a day-by-day schedule. The deterministic :class:`ItineraryAssembler`
then resolves those ids against the planning context, so selected flights and
hotels are grounded by construction and only the schedule needs validation.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import date, time
from decimal import Decimal
from typing import Protocol, TypeVar

from pydantic import BaseModel, Field

from agentic_travel.agents.base import Agent
from agentic_travel.agents.planning import PlanningContext
from agentic_travel.domain.fx import to_inr
from agentic_travel.domain.money import Currency, Money
from agentic_travel.graph.store import GraphStore
from agentic_travel.itinerary.models import Activity, DayPlan, Itinerary
from agentic_travel.services.flights.models import FlightOffer
from agentic_travel.services.hotels.models import HotelOffer

_SYSTEM = """\
You are an expert travel planner. Using ONLY the options provided, compose a
bookable itinerary. Rules:
- Reference flights, hotels, and points of interest only by the ids given.
- Select one outbound flight, one return flight, and one hotel per city.
- Schedule each day's activities within the POI opening hours, in a sensible
  geographic order, with realistic visit times and no overlaps.
- Respect the traveler's budget, party size, dates, food preference, and
  interests. Do not invent places or ids.
Return the structured plan."""


class PlannedActivity(BaseModel):
    """A scheduled POI visit proposed by the model."""

    poi_id: str
    start: time
    end: time
    notes: str = ""


class PlannedDay(BaseModel):
    """A single proposed day of the trip."""

    day_index: int
    date: date
    city_id: str
    activities: list[PlannedActivity] = Field(default_factory=list)
    notes: str = ""


class HotelChoice(BaseModel):
    """The hotel offer chosen for a city."""

    city_id: str
    hotel_offer_id: str


class SynthesisPlan(BaseModel):
    """The model's proposed itinerary, referencing offers and POIs by id."""

    title: str
    summary: str
    outbound_flight_id: str | None = None
    return_flight_id: str | None = None
    hotels: list[HotelChoice] = Field(default_factory=list)
    days: list[PlannedDay] = Field(default_factory=list)


def _context_payload(ctx: PlanningContext) -> dict[str, object]:
    """Build a compact, id-focused view of the context for the prompt."""
    return {
        "constraints": {
            "party_size": ctx.brief.party_size,
            "budget": ctx.brief.budget.model_dump(mode="json") if ctx.brief.budget else None,
            "food_preference": ctx.brief.food_preference.value,
            "interests": ctx.brief.interests,
            "occasion": ctx.brief.occasion,
            "start_date": ctx.brief.start_date.isoformat() if ctx.brief.start_date else None,
            "nights": ctx.brief.nights,
        },
        "outbound_flights": [f.model_dump(mode="json") for f in ctx.outbound_flights],
        "return_flights": [f.model_dump(mode="json") for f in ctx.return_flights],
        "cities": [
            {
                "city_id": c.city_id,
                "city_name": c.city_name,
                "nights": c.nights,
                "weather": c.weather.model_dump(mode="json"),
                "hotels": [h.model_dump(mode="json") for h in c.hotels],
                "candidate_pois": [p.model_dump(mode="json") for p in c.candidate_pois],
            }
            for c in ctx.cities
        ],
        "visas": [v.model_dump(mode="json") for v in ctx.visas],
    }


class SynthesizerAgent(Agent):
    """Asks the model to compose a `SynthesisPlan` from the planning context."""

    name = "synthesizer"

    def run(
        self,
        ctx: PlanningContext,
        *,
        model: str,
        feedback: list[str] | None = None,
    ) -> SynthesisPlan:
        """Generate a synthesis plan, optionally incorporating critic feedback."""
        with self._span():
            payload = _context_payload(ctx)
            prompt = "OPTIONS:\n" + json.dumps(payload, indent=2)
            if feedback:
                prompt += "\n\nFix these problems from the previous attempt:\n- " + "\n- ".join(
                    feedback
                )
            plan, _ = self._llm.generate_structured(
                model=model, system=_SYSTEM, prompt=prompt, schema=SynthesisPlan
            )
            return plan


class SynthesisStrategy(Protocol):
    """A strategy that proposes a `SynthesisPlan` for a planning context."""

    def propose(
        self, context: PlanningContext, *, feedback: list[str] | None = None
    ) -> SynthesisPlan:
        """Propose a plan, optionally addressing prior validation feedback."""
        ...


class LlmSynthesizer:
    """Synthesis strategy backed by the model via :class:`SynthesizerAgent`."""

    def __init__(self, agent: SynthesizerAgent, model: str) -> None:
        """Wrap a synthesizer agent and the model id it should use."""
        self._agent = agent
        self._model = model

    def propose(
        self, context: PlanningContext, *, feedback: list[str] | None = None
    ) -> SynthesisPlan:
        """Delegate to the agent's model call."""
        return self._agent.run(context, model=self._model, feedback=feedback)


class _HasOfferId(Protocol):
    offer_id: str


_OfferT = TypeVar("_OfferT", bound=_HasOfferId)


def _by_id(items: Sequence[_OfferT], wanted: str | None) -> _OfferT | None:
    """Return the item whose ``offer_id`` equals ``wanted``, else ``None``."""
    if wanted is None:
        return None
    return next((item for item in items if item.offer_id == wanted), None)


class ItineraryAssembler:
    """Resolves a `SynthesisPlan` against a context into a full `Itinerary`."""

    def __init__(self, store: GraphStore) -> None:
        """Store the graph used to resolve POI names and ticket prices."""
        self._store = store

    def assemble(
        self, plan: SynthesisPlan, ctx: PlanningContext, *, itinerary_id: str = "itin_draft"
    ) -> Itinerary:
        """Build the grounded itinerary described by ``plan``."""
        flights: list[FlightOffer] = []
        for selected in (
            _by_id(ctx.outbound_flights, plan.outbound_flight_id),
            _by_id(ctx.return_flights, plan.return_flight_id),
        ):
            if selected is not None:
                flights.append(selected)

        hotels = self._resolve_hotels(plan, ctx)
        days = [self._day(pd) for pd in plan.days]
        start_date = ctx.brief.start_date or (days[0].date if days else date(2026, 1, 1))
        end_date = max((d.date for d in days), default=start_date)
        estimated_total = _estimate_total(flights, hotels, days, ctx.brief.party_size)

        return Itinerary(
            itinerary_id=itinerary_id,
            title=plan.title,
            traveler_id=ctx.brief.traveler_id,
            party_size=ctx.brief.party_size,
            origin_city_id=ctx.origin_city_id or "",
            destination_city_ids=ctx.destination_city_ids,
            start_date=start_date,
            end_date=end_date,
            flights=flights,
            hotels=hotels,
            visa=ctx.visas,
            days=days,
            estimated_total=estimated_total,
            summary=plan.summary,
        )

    def _resolve_hotels(self, plan: SynthesisPlan, ctx: PlanningContext) -> list[HotelOffer]:
        cities = {c.city_id: c for c in ctx.cities}
        resolved: list[HotelOffer] = []
        for choice in plan.hotels:
            city = cities.get(choice.city_id)
            if city is None:
                continue
            offer = _by_id(city.hotels, choice.hotel_offer_id)
            if offer is not None:
                resolved.append(offer)
        return resolved

    def _day(self, planned: PlannedDay) -> DayPlan:
        activities = [
            Activity(
                poi_id=item.poi_id,
                name=(poi.name if (poi := self._store.get_poi(item.poi_id)) else item.poi_id),
                start=item.start,
                end=item.end,
                estimated_cost=poi.ticket_price if poi else None,
                notes=item.notes,
            )
            for item in planned.activities
        ]
        return DayPlan(
            day_index=planned.day_index,
            date=planned.date,
            city_id=planned.city_id,
            activities=activities,
            notes=planned.notes,
        )


def _estimate_total(
    flights: list[FlightOffer],
    hotels: list[HotelOffer],
    days: list[DayPlan],
    party_size: int,
) -> Money:
    """Estimate the trip total in INR (flights and activities scale by party size)."""
    total = Decimal("0")
    for flight in flights:
        total += to_inr(flight.price).amount * party_size
    for hotel in hotels:
        total += to_inr(hotel.total_price).amount
    for day in days:
        for activity in day.activities:
            if activity.estimated_cost is not None:
                total += to_inr(activity.estimated_cost).amount * party_size
    return Money(amount=total, currency=Currency.INR)
