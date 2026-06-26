from datetime import date, time
from decimal import Decimal

from agentic_travel.data.loader import load_default_graph_store
from agentic_travel.domain.money import Currency, Money
from agentic_travel.graph.store import InMemoryGraphStore
from agentic_travel.itinerary.models import Activity, DayPlan, Itinerary
from agentic_travel.itinerary.validation import IssueSeverity, validate_itinerary
from agentic_travel.services.visa.service import VisaService


def _valid_goa_itinerary() -> Itinerary:
    """A feasible one-day Goa itinerary used as the baseline for mutation tests."""
    visa = VisaService.from_default_dataset().assess("IN", "IN")
    day = DayPlan(
        day_index=1,
        date=date(2026, 12, 5),  # a Saturday
        city_id="city_goi",
        activities=[
            Activity(
                poi_id="poi_basilica_bom_jesus",
                name="Basilica of Bom Jesus",
                start=time(9, 30),
                end=time(11, 0),
                estimated_cost=Money(amount=Decimal("0"), currency=Currency.INR),
            ),
            Activity(
                poi_id="poi_baga_beach",
                name="Baga Beach",
                start=time(12, 0),
                end=time(14, 0),
                estimated_cost=Money(amount=Decimal("0"), currency=Currency.INR),
            ),
        ],
    )
    return Itinerary(
        itinerary_id="itin_1",
        title="A Day in Goa",
        traveler_id="tr_arjun",
        party_size=2,
        origin_city_id="city_bom",
        destination_city_ids=["city_goi"],
        start_date=date(2026, 12, 5),
        end_date=date(2026, 12, 5),
        flights=[],
        hotels=[],
        visa=[visa],
        days=[day],
        estimated_total=Money(amount=Decimal("40000"), currency=Currency.INR),
        summary="Quick getaway.",
    )


def _store() -> InMemoryGraphStore:
    return load_default_graph_store()


def test_valid_itinerary_has_no_errors() -> None:
    report = validate_itinerary(_valid_goa_itinerary(), _store())
    assert report.is_valid
    assert [i for i in report.issues if i.severity is IssueSeverity.ERROR] == []


def test_unknown_poi_is_error() -> None:
    itin = _valid_goa_itinerary()
    itin.days[0].activities[0].poi_id = "poi_hallucinated"
    report = validate_itinerary(itin, _store())
    assert not report.is_valid
    assert any(i.code == "unknown_poi" for i in report.issues)


def test_overlapping_activities_is_error() -> None:
    itin = _valid_goa_itinerary()
    itin.days[0].activities[1].start = time(10, 30)  # overlaps 09:30-11:00
    itin.days[0].activities[1].end = time(12, 0)
    report = validate_itinerary(itin, _store())
    assert any(i.code == "overlapping_activities" for i in report.issues)
    assert not report.is_valid


def test_outside_opening_hours_is_warning() -> None:
    itin = _valid_goa_itinerary()
    # Basilica closes 18:30; schedule it in the evening.
    itin.days[0].activities[0].start = time(19, 0)
    itin.days[0].activities[0].end = time(20, 0)
    report = validate_itinerary(itin, _store())
    issue = next(i for i in report.issues if i.code == "outside_opening_hours")
    assert issue.severity is IssueSeverity.WARNING


def test_over_budget_is_error() -> None:
    itin = _valid_goa_itinerary()
    budget = Money(amount=Decimal("10000"), currency=Currency.INR)
    report = validate_itinerary(itin, _store(), budget=budget)
    assert any(i.code == "over_budget" for i in report.issues)
    assert not report.is_valid


def test_packed_day_is_warning() -> None:
    itin = _valid_goa_itinerary()
    base = itin.days[0].activities[0]
    # 7 activities exceeds the default pace cap.
    itin.days[0].activities = [
        base.model_copy(update={"start": time(6 + n, 0), "end": time(6 + n, 30)})
        for n in range(7)
    ]
    report = validate_itinerary(itin, _store(), max_activities_per_day=6)
    assert any(i.code == "packed_day" for i in report.issues)


def test_day_count_mismatch_is_warning() -> None:
    itin = _valid_goa_itinerary()
    itin.end_date = date(2026, 12, 8)  # 4-day span but only one day planned
    report = validate_itinerary(itin, _store())
    assert any(i.code == "day_count_mismatch" for i in report.issues)


def test_nights_property() -> None:
    itin = _valid_goa_itinerary()
    itin.end_date = date(2026, 12, 8)
    assert itin.nights == 3


def test_invalid_activity_times_is_error() -> None:
    itin = _valid_goa_itinerary()
    itin.days[0].activities[0].start = time(11, 0)
    itin.days[0].activities[0].end = time(10, 0)
    report = validate_itinerary(itin, _store())
    assert any(i.code == "invalid_times" for i in report.issues)
    assert not report.is_valid
