from datetime import date, time

from agentic_travel.agents.coordinator import Coordinator, ModelConfig
from agentic_travel.agents.intent import _IntentOut
from agentic_travel.agents.models import BriefExtract, TripIntent
from agentic_travel.agents.synthesizer import PlannedActivity, PlannedDay, SynthesisPlan
from agentic_travel.data.loader import load_default_graph_store
from agentic_travel.llm.client import FakeLlmClient
from agentic_travel.services.flights.service import FlightService
from agentic_travel.services.hotels.service import HotelService
from agentic_travel.services.memory.service import MemoryService
from agentic_travel.services.visa.service import VisaService
from agentic_travel.services.weather.service import WeatherService


def _coordinator(fake: FakeLlmClient, *, max_repairs: int = 2) -> Coordinator:
    return Coordinator(
        llm=fake,
        store=load_default_graph_store(),
        flights=FlightService.from_default_dataset(),
        hotels=HotelService.from_default_dataset(),
        visa=VisaService.from_default_dataset(),
        weather=WeatherService.from_default_dataset(),
        memory=MemoryService.from_default_dataset(),
        models=ModelConfig(fast="fast", planner="planner"),
        max_repairs=max_repairs,
    )


def _intent_goa() -> _IntentOut:
    return _IntentOut(intent=TripIntent.ITINERARY, confidence=0.95, destination_hint="Goa")


def _brief_goa() -> BriefExtract:
    return BriefExtract(
        destination_query="Goa", start_date=date(2026, 12, 5), nights=1, party_size=2
    )


def _day(*activities: PlannedActivity) -> PlannedDay:
    return PlannedDay(
        day_index=1, date=date(2026, 12, 5), city_id="city_goi", activities=list(activities)
    )


_GOOD_ACTIVITIES = (
    PlannedActivity(poi_id="poi_basilica_bom_jesus", start=time(9, 30), end=time(11, 0)),
    PlannedActivity(poi_id="poi_baga_beach", start=time(12, 0), end=time(14, 0)),
)


def test_happy_path_produces_valid_itinerary() -> None:
    plan = SynthesisPlan(
        title="Goa Getaway", summary="Sun and heritage.", days=[_day(*_GOOD_ACTIVITIES)]
    )
    fake = FakeLlmClient(objects=[_intent_goa(), _brief_goa(), plan])
    result = _coordinator(fake).plan_itinerary("Plan 1 night in Goa", traveler_id="tr_arjun")

    assert result.itinerary is not None
    assert result.validation.is_valid
    assert result.attempts == 1
    assert result.resolved_city_ids == ["city_goi"]
    # Personalization flowed through: origin came from the traveler's home city.
    assert result.itinerary.origin_city_id == "city_bom"


def test_repair_loop_recovers_from_invalid_first_plan() -> None:
    bad = SynthesisPlan(
        title="Clashing",
        summary="Overlaps.",
        days=[
            _day(
                PlannedActivity(poi_id="poi_baga_beach", start=time(10, 0), end=time(12, 0)),
                PlannedActivity(
                    poi_id="poi_basilica_bom_jesus", start=time(11, 0), end=time(13, 0)
                ),
            )
        ],
    )
    good = SynthesisPlan(
        title="Fixed", summary="No overlaps.", days=[_day(*_GOOD_ACTIVITIES)]
    )
    fake = FakeLlmClient(objects=[_intent_goa(), _brief_goa(), bad, good])
    result = _coordinator(fake).plan_itinerary("1 night in Goa", traveler_id="tr_arjun")

    assert result.attempts == 2
    assert result.validation.is_valid
    assert result.itinerary is not None and result.itinerary.title == "Fixed"


def test_missing_destination_asks_for_clarification() -> None:
    fake = FakeLlmClient(
        objects=[
            _IntentOut(intent=TripIntent.ITINERARY, confidence=0.6),
            BriefExtract(destination_query=""),
        ]
    )
    result = _coordinator(fake).plan_itinerary("I want to travel somewhere", traveler_id="tr_arjun")
    assert result.itinerary is None
    assert "destination" in result.brief.clarifications_needed


def test_unresolved_destination_reports_error() -> None:
    fake = FakeLlmClient(
        objects=[
            _IntentOut(intent=TripIntent.ITINERARY, confidence=0.8, destination_hint="Atlantis"),
            BriefExtract(destination_query="Atlantis", nights=2),
        ]
    )
    result = _coordinator(fake).plan_itinerary("2 nights in Atlantis", traveler_id="tr_arjun")
    assert result.itinerary is None
    assert any(i.code == "unresolved_destination" for i in result.validation.issues)
