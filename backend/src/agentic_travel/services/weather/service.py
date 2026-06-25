"""Seasonal climate briefs over a curated dataset."""

from __future__ import annotations

from importlib import resources
from pathlib import Path

from pydantic import BaseModel

from agentic_travel.services.weather.models import Season, WeatherBrief


class _CityClimate(BaseModel):
    city_id: str
    months: list[WeatherBrief]


class _ClimateDataset(BaseModel):
    cities: list[_CityClimate]


class WeatherService:
    """Returns seasonal climate briefs; neutral fallback when data is missing."""

    def __init__(self, dataset: _ClimateDataset) -> None:
        """Index briefs by (city_id, month)."""
        self._briefs: dict[tuple[str, int], WeatherBrief] = {}
        for city in dataset.cities:
            for brief in city.months:
                self._briefs[(city.city_id, brief.month)] = brief

    @classmethod
    def from_default_dataset(cls) -> WeatherService:
        """Load the packaged climate dataset."""
        resource = resources.files("agentic_travel.data") / "climate.json"
        dataset = _ClimateDataset.model_validate_json(
            Path(str(resource)).read_text(encoding="utf-8")
        )
        return cls(dataset)

    def brief(self, city_id: str, month: int) -> WeatherBrief:
        """Return the climate brief for a city/month, or a neutral fallback."""
        known = self._briefs.get((city_id, month))
        if known is not None:
            return known
        return WeatherBrief(
            city_id=city_id,
            month=month,
            season=Season.SHOULDER,
            avg_high_c=25.0,
            avg_low_c=18.0,
            rain_probability=0.3,
            advisory="Detailed climate data unavailable for this destination.",
            is_recommended=True,
        )
