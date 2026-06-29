"""Models for city practical guidance: getting around and events."""

from __future__ import annotations

from pydantic import BaseModel, Field


class GuideEvent(BaseModel):
    """A notable happening in a city, optionally tied to a month."""

    name: str
    month: int = Field(ge=0, le=12)  # 0 = year-round
    blurb: str = ""


class CityGuide(BaseModel):
    """Practical guidance for a city."""

    city_id: str
    getting_around: str = ""
    events: list[GuideEvent] = Field(default_factory=list)
