from decimal import Decimal

from agentic_travel.domain.geo import GeoPoint
from agentic_travel.domain.money import Currency, Money
from agentic_travel.graph.models import (
    POI,
    Edge,
    EdgeKind,
    OpeningHours,
    POICategory,
    TransportMode,
)


def test_poi_construction() -> None:
    poi = POI(
        id="poi_gateway_of_india",
        name="Gateway of India",
        city_id="city_bom",
        location=GeoPoint(lat=18.9220, lng=72.8347),
        category=POICategory.LANDMARK,
        typical_visit_minutes=60,
        ticket_price=Money(amount=Decimal("0"), currency=Currency.INR),
        rating=4.6,
        opening_hours=OpeningHours(opens="06:00", closes="22:00", days=[0, 1, 2, 3, 4, 5, 6]),
        tags=["iconic", "waterfront"],
    )
    assert poi.category is POICategory.LANDMARK
    assert poi.typical_visit_minutes == 60


def test_connected_by_edge() -> None:
    edge = Edge(
        source_id="city_bom",
        target_id="city_goi",
        kind=EdgeKind.CONNECTED_BY,
        distance_km=590.0,
        mode=TransportMode.FLIGHT,
        duration_minutes=90,
    )
    assert edge.kind is EdgeKind.CONNECTED_BY
    assert edge.mode is TransportMode.FLIGHT
