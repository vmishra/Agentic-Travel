"""Models for restaurant recommendations."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

from agentic_travel.domain.geo import GeoPoint
from agentic_travel.domain.traveler import BudgetTier


class Meal(StrEnum):
    """A meal a restaurant is suited to."""

    BREAKFAST = "breakfast"
    LUNCH = "lunch"
    DINNER = "dinner"


class Restaurant(BaseModel):
    """A dining option within a city."""

    id: str
    city_id: str
    name: str
    cuisine: str
    neighborhood: str = ""
    price_tier: BudgetTier
    meals: list[Meal] = Field(default_factory=list)
    dietary: list[str] = Field(default_factory=list)
    why: str = ""
    rating: float = Field(ge=0.0, le=5.0)
    location: GeoPoint | None = None
