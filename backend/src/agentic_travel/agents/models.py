"""Structured inputs and outputs exchanged between planning agents."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field

from agentic_travel.domain.money import Money
from agentic_travel.domain.traveler import BudgetTier, FoodPreference


class TripIntent(StrEnum):
    """The user's high-level goal for a conversation turn."""

    INQUIRY = "inquiry"
    ITINERARY = "itinerary"
    POST_TRAVEL = "post_travel"


class IntentResult(BaseModel):
    """Classified intent for a user message."""

    intent: TripIntent
    confidence: float = Field(ge=0.0, le=1.0)
    destination_hint: str | None = None
    raw_query: str


class TripBrief(BaseModel):
    """The enriched, structured brief that drives itinerary planning.

    Produced by the enrichment agent by combining what the user said with the
    traveler's long-term profile. ``clarifications_needed`` lists any critical
    slot still missing, which the coordinator can surface as a question.
    """

    intent: TripIntent
    traveler_id: str | None = None
    passport_country: str = "IN"
    origin_city_id: str | None = None
    destination_query: str
    start_date: date | None = None
    nights: int | None = None
    party_size: int = Field(default=1, ge=1)
    budget: Money | None = None
    budget_tier: BudgetTier = BudgetTier.MID_RANGE
    food_preference: FoodPreference = FoodPreference.NONE
    interests: list[str] = Field(default_factory=list)
    occasion: str | None = None
    clarifications_needed: list[str] = Field(default_factory=list)


class BriefExtract(BaseModel):
    """Raw slots extracted from the user's message by the enrichment model."""

    destination_query: str = ""
    start_date: date | None = None
    nights: int | None = None
    party_size: int | None = None
    budget_amount: Decimal | None = None
    budget_currency: str | None = None
    occasion: str | None = None
    interests: list[str] = Field(default_factory=list)


class ConversationState(BaseModel):
    """Slots accumulated across conversation turns for one planning session.

    Each message contributes whatever it specifies; values persist until the
    traveler changes them, so a destination and dates given in separate messages
    combine into one plan.
    """

    destination_city_ids: list[str] = Field(default_factory=list)
    start_date: date | None = None
    nights: int | None = None
    party_size: int | None = None
    budget: Money | None = None
    occasion: str | None = None
    interests: list[str] = Field(default_factory=list)
