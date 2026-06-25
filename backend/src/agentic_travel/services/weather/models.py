"""Models for climate/weather briefs."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class Season(StrEnum):
    """Coarse travel season."""

    WINTER = "winter"
    SUMMER = "summer"
    MONSOON = "monsoon"
    SHOULDER = "shoulder"


class WeatherBrief(BaseModel):
    """Seasonal climate summary for a city in a given month."""

    city_id: str
    month: int = Field(ge=1, le=12)
    season: Season
    avg_high_c: float
    avg_low_c: float
    rain_probability: float = Field(ge=0.0, le=1.0)
    advisory: str
    is_recommended: bool
