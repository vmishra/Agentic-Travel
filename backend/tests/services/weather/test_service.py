from agentic_travel.services.weather.models import Season
from agentic_travel.services.weather.service import WeatherService


def _service() -> WeatherService:
    return WeatherService.from_default_dataset()


def test_peak_season_recommended() -> None:
    brief = _service().brief("city_goi", 1)
    assert brief.season is Season.WINTER
    assert brief.is_recommended is True
    assert brief.rain_probability < 0.1


def test_monsoon_not_recommended() -> None:
    brief = _service().brief("city_goi", 7)
    assert brief.season is Season.MONSOON
    assert brief.is_recommended is False
    assert brief.rain_probability > 0.5


def test_unknown_city_returns_neutral_brief() -> None:
    brief = _service().brief("city_none", 5)
    assert brief.city_id == "city_none"
    assert "unavailable" in brief.advisory.lower()
