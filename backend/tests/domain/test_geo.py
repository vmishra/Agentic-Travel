from agentic_travel.domain.geo import GeoPoint


def test_distance_between_known_points() -> None:
    # New Delhi -> Mumbai is roughly 1150 km.
    delhi = GeoPoint(lat=28.6139, lng=77.2090)
    mumbai = GeoPoint(lat=19.0760, lng=72.8777)
    assert 1100 <= delhi.distance_km(mumbai) <= 1200


def test_distance_to_self_is_zero() -> None:
    point = GeoPoint(lat=10.0, lng=20.0)
    assert point.distance_km(point) == 0.0
