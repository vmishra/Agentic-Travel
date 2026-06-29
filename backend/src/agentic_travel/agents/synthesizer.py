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
from agentic_travel.agents.models import TripBrief
from agentic_travel.agents.planning import PlanningContext
from agentic_travel.domain.fx import to_inr
from agentic_travel.domain.geo import GeoPoint
from agentic_travel.domain.money import Currency, Money
from agentic_travel.graph.store import GraphStore
from agentic_travel.itinerary.models import (
    Activity,
    CostBreakdown,
    DayPlan,
    DiningPick,
    Itinerary,
    TripEvent,
)
from agentic_travel.services.dining.models import Meal
from agentic_travel.services.dining.service import DiningService
from agentic_travel.services.flights.models import FlightOffer
from agentic_travel.services.guide.service import GuideService
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

    def __init__(
        self,
        store: GraphStore,
        dining: DiningService | None = None,
        guide: GuideService | None = None,
    ) -> None:
        """Wire the graph plus optional dining and city-guide services."""
        self._store = store
        self._dining = dining
        self._guide = guide

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
        used_restaurants: set[str] = set()
        days = [self._day(pd, ctx.brief, used_restaurants) for pd in plan.days]
        start_date = ctx.brief.start_date or (days[0].date if days else date(2026, 1, 1))
        end_date = max((d.date for d in days), default=start_date)
        breakdown = _cost_breakdown(flights, hotels, days, ctx.brief.party_size)

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
            estimated_total=breakdown.total,
            summary=plan.summary,
            style_tags=_style_tags(ctx),
            highlights=_highlights(days),
            season_note=_season_note(ctx),
            getting_around=self._getting_around(ctx),
            events=self._events(ctx),
            cost_breakdown=breakdown,
        )

    def _getting_around(self, ctx: PlanningContext) -> str | None:
        if self._guide is None or not ctx.destination_city_ids:
            return None
        return self._guide.getting_around(ctx.destination_city_ids[0])

    def _events(self, ctx: PlanningContext) -> list[TripEvent]:
        if self._guide is None:
            return []
        month = ctx.brief.start_date.month if ctx.brief.start_date else 0
        seen: set[str] = set()
        events: list[TripEvent] = []
        for city_id in ctx.destination_city_ids:
            for event in self._guide.events_for(city_id, month):
                if event.name not in seen:
                    seen.add(event.name)
                    events.append(TripEvent(name=event.name, blurb=event.blurb))
        return events[:4]

    def _dining_for(
        self, city_id: str, brief: TripBrief, used: set[str]
    ) -> list[DiningPick]:
        if self._dining is None:
            return []
        picks: list[DiningPick] = []
        for meal in (Meal.LUNCH, Meal.DINNER):
            restaurant = self._dining.recommend(
                city_id,
                meal=meal,
                food_preference=brief.food_preference,
                budget_tier=brief.budget_tier,
                exclude_ids=used,
            )
            if restaurant is not None:
                used.add(restaurant.id)
                picks.append(
                    DiningPick(
                        name=restaurant.name,
                        cuisine=restaurant.cuisine,
                        neighborhood=restaurant.neighborhood,
                        meal=meal.value,
                        price_tier=restaurant.price_tier.value,
                        why=restaurant.why,
                        rating=restaurant.rating,
                    )
                )
        return picks

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

    def _day(self, planned: PlannedDay, brief: TripBrief, used: set[str]) -> DayPlan:
        activities: list[Activity] = []
        for item in planned.activities:
            poi = self._store.get_poi(item.poi_id)
            activities.append(
                Activity(
                    poi_id=item.poi_id,
                    name=poi.name if poi else item.poi_id,
                    start=item.start,
                    end=item.end,
                    category=poi.category.value if poi else "",
                    location=poi.location if poi else None,
                    rating=poi.rating if poi else None,
                    estimated_cost=poi.ticket_price if poi else None,
                    notes=item.notes,
                )
            )
        # Travel time and mode between consecutive stops — a realism/trust signal.
        for current, nxt in zip(activities, activities[1:], strict=False):
            current.travel_minutes_to_next = _travel_minutes(current.location, nxt.location)
            current.travel_mode_to_next = _travel_mode(current.location, nxt.location)
        return DayPlan(
            day_index=planned.day_index,
            date=planned.date,
            city_id=planned.city_id,
            theme=_day_theme(activities),
            activities=activities,
            dining=self._dining_for(planned.city_id, brief, used),
            notes=planned.notes,
        )


def _travel_minutes(origin: GeoPoint | None, destination: GeoPoint | None) -> int | None:
    """Estimate door-to-door minutes between stops at ~22 km/h urban average."""
    if origin is None or destination is None:
        return None
    return max(5, round(origin.distance_km(destination) / 22 * 60))


def _travel_mode(origin: GeoPoint | None, destination: GeoPoint | None) -> str | None:
    """Return a plausible transport mode based on the hop distance."""
    if origin is None or destination is None:
        return None
    km = origin.distance_km(destination)
    if km < 1.2:
        return "walk"
    if km < 12:
        return "taxi"
    return "transit"


_THEME_BY_CATEGORY: dict[str, str] = {
    "beach": "Sun, sand & sea",
    "landmark": "Icons & landmarks",
    "museum": "Art & history",
    "religious": "Heritage & quiet corners",
    "market": "Markets & street life",
    "nature": "Open air & nature",
    "entertainment": "Lights & late nights",
    "adventure": "Out for adventure",
}


def _day_theme(activities: list[Activity]) -> str:
    """Name the day from the kind of places it leans on."""
    counts: dict[str, int] = {}
    for activity in activities:
        if activity.category:
            counts[activity.category] = counts.get(activity.category, 0) + 1
    if not counts:
        return "A day at your pace"
    top = max(counts, key=lambda c: counts[c])
    return _THEME_BY_CATEGORY.get(top, "Highlights of the day")


def _cost_breakdown(
    flights: list[FlightOffer],
    hotels: list[HotelOffer],
    days: list[DayPlan],
    party_size: int,
) -> CostBreakdown:
    """Split the estimated cost into flights, stays, and activities (all INR)."""
    flights_inr = sum((to_inr(f.price).amount * party_size for f in flights), Decimal("0"))
    stays_inr = sum((to_inr(h.total_price).amount for h in hotels), Decimal("0"))
    activities_inr = sum(
        (
            to_inr(a.estimated_cost).amount * party_size
            for day in days
            for a in day.activities
            if a.estimated_cost is not None
        ),
        Decimal("0"),
    )
    total = flights_inr + stays_inr + activities_inr
    num_days = max(1, len(days))

    def _inr(amount: Decimal) -> Money:
        return Money(amount=amount.quantize(Decimal("1")), currency=Currency.INR)

    return CostBreakdown(
        flights=_inr(flights_inr),
        stays=_inr(stays_inr),
        activities=_inr(activities_inr),
        total=_inr(total),
        per_person=_inr(total / party_size),
        per_day=_inr(total / num_days),
        note="Excludes meals, local transport, and a ~15% buffer for upgrades and spontaneity.",
    )


def _style_tags(ctx: PlanningContext) -> list[str]:
    """Derive a few descriptive trip tags from the brief."""
    brief = ctx.brief
    tags: list[str] = [brief.budget_tier.value.replace("_", " ").title()]
    if brief.party_size >= 4:
        tags.append("Group")
    elif brief.party_size == 2:
        tags.append("For two")
    if brief.occasion:
        tags.append(brief.occasion.title())
    for interest in brief.interests[:2]:
        tags.append(interest.title())
    return list(dict.fromkeys(tags))[:4]


def _highlights(days: list[DayPlan]) -> list[str]:
    """Return the three best-rated experiences across the trip."""
    activities = [a for day in days for a in day.activities if a.rating is not None]
    activities.sort(key=lambda a: a.rating or 0.0, reverse=True)
    seen: set[str] = set()
    names: list[str] = []
    for activity in activities:
        if activity.name not in seen:
            seen.add(activity.name)
            names.append(activity.name)
        if len(names) == 3:
            break
    return names


def _season_note(ctx: PlanningContext) -> str | None:
    """Return a one-line seasonal note for the first destination."""
    if not ctx.cities:
        return None
    city = ctx.cities[0]
    weather = city.weather
    return (
        f"{weather.season.value.title()} in {city.city_name}: "
        f"highs around {round(weather.avg_high_c)}°C. {weather.advisory}"
    )
