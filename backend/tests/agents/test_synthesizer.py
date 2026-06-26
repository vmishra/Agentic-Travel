from datetime import date, time

from agentic_travel.agents.models import TripBrief, TripIntent
from agentic_travel.agents.planning import OptionsGatherer, PlanningContext
from agentic_travel.agents.synthesizer import (
    HotelChoice,
    ItineraryAssembler,
    PlannedActivity,
    PlannedDay,
    SynthesisPlan,
    SynthesizerAgent,
)
from agentic_travel.data.loader import load_default_graph_store
from agentic_travel.domain.money import Currency
from agentic_travel.domain.traveler import BudgetTier
from agentic_travel.itinerary.validation import validate_itinerary
from agentic_travel.llm.client import FakeLlmClient
from agentic_travel.observability.span import SpanKind
from agentic_travel.observability.tracer import Tracer
from agentic_travel.services.flights.service import FlightService
from agentic_travel.services.hotels.service import HotelService
from agentic_travel.services.visa.service import VisaService
from agentic_travel.services.weather.service import WeatherService


def _context() -> PlanningContext:
    gatherer = OptionsGatherer(
        store=load_default_graph_store(),
        flights=FlightService.from_default_dataset(),
        hotels=HotelService.from_default_dataset(),
        visa=VisaService.from_default_dataset(),
        weather=WeatherService.from_default_dataset(),
    )
    brief = TripBrief(
        intent=TripIntent.ITINERARY,
        origin_city_id="city_bom",
        destination_query="Goa",
        start_date=date(2026, 12, 5),
        nights=1,
        party_size=2,
        budget_tier=BudgetTier.PREMIUM,
    )
    return gatherer.gather(brief, ["city_goi"])


def _plan_from(ctx: PlanningContext) -> SynthesisPlan:
    goa = ctx.cities[0]
    return SynthesisPlan(
        title="A Day in Goa",
        summary="Beaches and heritage.",
        outbound_flight_id=ctx.outbound_flights[0].offer_id,
        return_flight_id=ctx.return_flights[0].offer_id,
        hotels=[HotelChoice(city_id="city_goi", hotel_offer_id=goa.hotels[0].offer_id)],
        days=[
            PlannedDay(
                day_index=1,
                date=date(2026, 12, 5),
                city_id="city_goi",
                activities=[
                    PlannedActivity(
                        poi_id="poi_basilica_bom_jesus", start=time(9, 30), end=time(11, 0)
                    ),
                    PlannedActivity(poi_id="poi_baga_beach", start=time(12, 0), end=time(14, 0)),
                ],
            )
        ],
    )


def test_assembler_produces_grounded_valid_itinerary() -> None:
    ctx = _context()
    plan = _plan_from(ctx)
    store = load_default_graph_store()
    itinerary = ItineraryAssembler(store).assemble(plan, ctx, itinerary_id="itin_test")

    assert itinerary.title == "A Day in Goa"
    assert len(itinerary.flights) == 2  # outbound + return resolved
    assert len(itinerary.hotels) == 1
    assert itinerary.estimated_total.currency is Currency.INR
    assert itinerary.estimated_total.amount > 0
    # Activity names were resolved from the graph, not echoed ids.
    assert itinerary.days[0].activities[0].name == "Basilica of Bom Jesus"

    report = validate_itinerary(itinerary, store)
    assert report.is_valid


def test_assembler_ignores_unknown_offer_ids() -> None:
    ctx = _context()
    plan = _plan_from(ctx)
    plan.outbound_flight_id = "fl_nonexistent"
    plan.hotels[0].hotel_offer_id = "ht_nonexistent"
    itinerary = ItineraryAssembler(load_default_graph_store()).assemble(plan, ctx)
    assert len(itinerary.flights) == 1  # only the return flight resolved
    assert itinerary.hotels == []


def test_synthesizer_agent_returns_plan_and_traces() -> None:
    ctx = _context()
    plan = _plan_from(ctx)
    fake = FakeLlmClient(objects=[plan])
    tracer = Tracer()
    result = SynthesizerAgent(fake, tracer=tracer).run(ctx, model="planner")
    assert result.title == "A Day in Goa"
    spans = tracer.finished_spans()
    assert any(s.name == "synthesizer" and s.kind is SpanKind.AGENT for s in spans)
