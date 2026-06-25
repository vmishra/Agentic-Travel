from agentic_travel.domain.geo import GeoPoint
from agentic_travel.graph.models import (
    POI,
    City,
    Country,
    Edge,
    EdgeKind,
    POICategory,
    Region,
    TransportMode,
)
from agentic_travel.graph.store import GraphData, InMemoryGraphStore


def _sample() -> GraphData:
    return GraphData(
        regions=[Region(id="reg_sa", name="South Asia")],
        countries=[Country(id="ctry_in", name="India", region_id="reg_sa", iso_code="IN")],
        cities=[
            City(
                id="city_bom",
                name="Mumbai",
                country_id="ctry_in",
                location=GeoPoint(lat=19.0760, lng=72.8777),
                timezone="Asia/Kolkata",
            ),
            City(
                id="city_goi",
                name="Goa",
                country_id="ctry_in",
                location=GeoPoint(lat=15.2993, lng=74.1240),
                timezone="Asia/Kolkata",
            ),
        ],
        pois=[
            POI(
                id="poi_gateway",
                name="Gateway of India",
                city_id="city_bom",
                location=GeoPoint(lat=18.9220, lng=72.8347),
                category=POICategory.LANDMARK,
                typical_visit_minutes=60,
                rating=4.6,
            )
        ],
        edges=[
            Edge(source_id="ctry_in", target_id="city_bom", kind=EdgeKind.CONTAINS),
            Edge(source_id="ctry_in", target_id="city_goi", kind=EdgeKind.CONTAINS),
            Edge(source_id="city_bom", target_id="poi_gateway", kind=EdgeKind.CONTAINS),
            Edge(
                source_id="city_bom",
                target_id="city_goi",
                kind=EdgeKind.CONNECTED_BY,
                distance_km=590.0,
                mode=TransportMode.FLIGHT,
                duration_minutes=90,
            ),
        ],
    )


def test_lookup_and_traversal() -> None:
    store = InMemoryGraphStore(_sample())
    city = store.get_city("city_bom")
    assert city is not None
    assert city.name == "Mumbai"
    assert {c.id for c in store.cities_in_country("ctry_in")} == {"city_bom", "city_goi"}
    assert [p.id for p in store.pois_in_city("city_bom")] == ["poi_gateway"]


def test_connections_filtered_by_mode() -> None:
    store = InMemoryGraphStore(_sample())
    flights = store.connections_from("city_bom", mode=TransportMode.FLIGHT)
    assert len(flights) == 1
    assert flights[0].target_id == "city_goi"
    assert store.connections_from("city_bom", mode=TransportMode.CAR) == []


def test_missing_node_returns_none() -> None:
    store = InMemoryGraphStore(_sample())
    assert store.get_city("city_unknown") is None
