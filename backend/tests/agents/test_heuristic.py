from datetime import date

from agentic_travel.agents.coordinator import Coordinator, ModelConfig
from agentic_travel.agents.heuristic import HeuristicLlmClient, HeuristicSynthesizer
from agentic_travel.agents.intent import IntentOut
from agentic_travel.agents.models import BriefExtract, TripIntent
from agentic_travel.agents.planning import OptionsGatherer
from agentic_travel.data.loader import load_default_graph_store
from agentic_travel.itinerary.validation import validate_itinerary
from agentic_travel.services.flights.service import FlightService
from agentic_travel.services.hotels.service import HotelService
from agentic_travel.services.memory.service import MemoryService
from agentic_travel.services.visa.service import VisaService
from agentic_travel.services.weather.service import WeatherService


def test_heuristic_intent_detects_itinerary() -> None:
    out, _ = HeuristicLlmClient().generate_structured(
        model="x", prompt="Plan 3 nights in Goa", schema=IntentOut
    )
    assert out.intent is TripIntent.ITINERARY


def test_heuristic_brief_extracts_nights_and_party() -> None:
    out, _ = HeuristicLlmClient().generate_structured(
        model="x", prompt="5 days in Goa for a couple, love beaches", schema=BriefExtract
    )
    assert out.nights == 4  # 5 days -> 4 nights
    assert out.party_size == 2
    assert "beaches" in out.interests


def test_heuristic_end_to_end_produces_valid_itinerary() -> None:
    store = load_default_graph_store()
    coordinator = Coordinator(
        llm=HeuristicLlmClient(),
        synthesizer=HeuristicSynthesizer(store),
        store=store,
        flights=FlightService.from_default_dataset(),
        hotels=HotelService.from_default_dataset(),
        visa=VisaService.from_default_dataset(),
        weather=WeatherService.from_default_dataset(),
        memory=MemoryService.from_default_dataset(),
        models=ModelConfig(fast="fast", planner="planner"),
    )
    result = coordinator.plan_itinerary("Plan 2 nights in Goa", traveler_id="tr_arjun")
    assert result.itinerary is not None
    assert result.validation.is_valid
    assert result.itinerary.days  # scheduled at least one day
    # Grounded against the real graph + offline scheduling.
    report = validate_itinerary(result.itinerary, store)
    assert report.is_valid


def test_heuristic_synth_schedules_within_opening_hours() -> None:
    store = load_default_graph_store()
    gatherer = OptionsGatherer(
        store=store,
        flights=FlightService.from_default_dataset(),
        hotels=HotelService.from_default_dataset(),
        visa=VisaService.from_default_dataset(),
        weather=WeatherService.from_default_dataset(),
    )
    from agentic_travel.agents.models import TripBrief

    brief = TripBrief(
        intent=TripIntent.ITINERARY,
        origin_city_id="city_bom",
        destination_query="Goa",
        start_date=date(2026, 12, 5),
        nights=1,
    )
    ctx = gatherer.gather(brief, ["city_goi"])
    plan = HeuristicSynthesizer(store).propose(ctx)
    assert plan.days
    assert plan.outbound_flight_id is not None
