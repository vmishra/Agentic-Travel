import re
from datetime import date

from agentic_travel.domain.money import Currency
from agentic_travel.services.flights.models import (
    CabinClass,
    FareTier,
    FlightSearchRequest,
)
from agentic_travel.services.flights.service import FlightService


def _service() -> FlightService:
    return FlightService.from_default_dataset()


def test_search_returns_tiered_offers_sorted_by_price() -> None:
    service = _service()
    request = FlightSearchRequest(
        origin_city_id="city_bom",
        destination_city_id="city_goi",
        departure_date=date(2026, 9, 12),
    )
    offers = service.search(request)
    assert 3 <= len(offers) <= 4
    prices = [o.price.amount for o in offers]
    assert prices == sorted(prices)
    assert offers[0].price.currency is Currency.INR
    assert {o.fare_tier for o in offers} <= set(FareTier)
    assert offers[0].fare_tier is FareTier.SAVER
    seg = offers[0].segments[0]
    # Flight numbers look real: IATA code (letters/digits) + number, e.g. "6E 437".
    assert re.fullmatch(r"[A-Z0-9]{2,3} \d{3}", seg.flight_number)


def test_search_is_deterministic() -> None:
    service = _service()
    request = FlightSearchRequest(
        origin_city_id="city_bom",
        destination_city_id="city_dxb",
        departure_date=date(2026, 9, 12),
    )
    first = service.search(request)
    second = service.search(request)
    assert [o.model_dump() for o in first] == [o.model_dump() for o in second]


def test_unknown_route_returns_empty() -> None:
    service = _service()
    request = FlightSearchRequest(
        origin_city_id="city_bom",
        destination_city_id="city_unknown",
        departure_date=date(2026, 9, 12),
    )
    assert service.search(request) == []


def test_business_cabin_costs_more_than_economy() -> None:
    service = _service()
    base = FlightSearchRequest(
        origin_city_id="city_bom", destination_city_id="city_goi", departure_date=date(2026, 9, 12)
    )
    business = FlightSearchRequest(
        origin_city_id="city_bom",
        destination_city_id="city_goi",
        departure_date=date(2026, 9, 12),
        cabin=CabinClass.BUSINESS,
    )
    assert service.search(business)[0].price.amount > service.search(base)[0].price.amount
