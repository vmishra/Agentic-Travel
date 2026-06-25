"""Traveler profile and preference vocabulary."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class FoodPreference(StrEnum):
    """Dietary preference used to filter dining and activities."""

    VEGETARIAN = "vegetarian"
    VEGAN = "vegan"
    HALAL = "halal"
    JAIN = "jain"
    NONE = "none"


class BudgetTier(StrEnum):
    """Coarse budget band guiding flight, hotel, and activity selection."""

    BUDGET = "budget"
    MID_RANGE = "mid_range"
    PREMIUM = "premium"
    LUXURY = "luxury"


class TravelerProfile(BaseModel):
    """A traveler's long-term profile used for personalization."""

    traveler_id: str
    display_name: str
    home_city_id: str
    passport_country: str = Field(min_length=2, max_length=2)
    food_preference: FoodPreference = FoodPreference.NONE
    budget_tier: BudgetTier = BudgetTier.MID_RANGE
    loyalty_programs: list[str] = Field(default_factory=list)
    visited_city_ids: list[str] = Field(default_factory=list)
    interests: list[str] = Field(default_factory=list)
