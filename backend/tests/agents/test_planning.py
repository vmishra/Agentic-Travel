from datetime import date

from agentic_travel.agents.destination import DestinationResolver
from agentic_travel.agents.models import TripBrief, TripIntent
from agentic_travel.agents.planning import OptionsGatherer, _allocate_nights
from agentic_travel.data.loader import load_default_graph_store
from agentic_travel.domain.traveler import BudgetTier
from agentic_travel.observability.span import SpanKind
from agentic_travel.observability.tracer import Tracer
from agentic_travel.services.flights.service import FlightService
from agentic_travel.services.hotels.service import HotelService
from agentic_travel.services.visa.service import VisaService
from agentic_travel.services.weather.service import WeatherService


def _gatherer(tracer: Tracer | None = None) -> OptionsGatherer:
    return OptionsGatherer(
        store=load_default_graph_store(),
        flights=FlightService.from_default_dataset(),
        hotels=HotelService.from_default_dataset(),
        visa=VisaService.from_default_dataset(),
        weather=WeatherService.from_default_dataset(),
        tracer=tracer,
    )


def _brief(**overrides: object) -> TripBrief:
    base: dict[str, object] = {
        "intent": TripIntent.ITINERARY,
        "passport_country": "IN",
        "origin_city_id": "city_bom",
        "destination_query": "Goa",
        "start_date": date(2026, 12, 5),
        "nights": 3,
        "budget_tier": BudgetTier.PREMIUM,
        "interests": ["beaches"],
    }
    base.update(overrides)
    return TripBrief(**base)  # type: ignore[arg-type]


# --- destination resolver ----------------------------------------------------


def test_resolver_matches_city() -> None:
    resolver = DestinationResolver(load_default_graph_store())
    assert resolver.resolve("I want to go to Goa") == ["city_goi"]


def test_resolver_expands_country_to_cities() -> None:
    resolver = DestinationResolver(load_default_graph_store())
    assert set(resolver.resolve("a trip around India")) == {"city_bom", "city_goi"}


def test_resolver_unknown_is_empty() -> None:
    resolver = DestinationResolver(load_default_graph_store())
    assert resolver.resolve("Antarctica") == []


# --- nights allocation -------------------------------------------------------


def test_allocate_nights_even_and_remainder() -> None:
    assert _allocate_nights(6, 2) == [3, 3]
    assert _allocate_nights(5, 2) == [3, 2]
    assert _allocate_nights(3, 1) == [3]


# --- options gatherer --------------------------------------------------------


def test_gather_single_city_context() -> None:
    ctx = _gatherer().gather(_brief(), ["city_goi"])
    assert ctx.outbound_flights  # city_bom -> city_goi exists
    assert ctx.return_flights
    assert len(ctx.cities) == 1
    goa = ctx.cities[0]
    assert goa.city_name == "Goa"
    assert goa.nights == 3
    assert goa.hotels
    assert goa.candidate_pois
    assert ctx.visas and ctx.visas[0].category.value == "not_required_domestic"


def test_gather_emits_tool_spans() -> None:
    tracer = Tracer()
    _gatherer(tracer).gather(_brief(), ["city_goi"])
    tool_spans = [s for s in tracer.finished_spans() if s.kind is SpanKind.TOOL]
    names = {s.name for s in tool_spans}
    assert any(n.startswith("hotels:") for n in names)
    assert any(n.startswith("flights:") for n in names)
    assert any(n.startswith("visa:") for n in names)


def test_gather_without_dates_skips_flights() -> None:
    ctx = _gatherer().gather(_brief(start_date=None), ["city_goi"])
    assert ctx.outbound_flights == []
    assert ctx.cities[0].hotels  # hotels still gathered
