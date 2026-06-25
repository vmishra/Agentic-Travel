"""Request and response models for flight search."""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from agentic_travel.domain.money import Money


class CabinClass(StrEnum):
    """Cabin of travel."""

    ECONOMY = "economy"
    PREMIUM_ECONOMY = "premium_economy"
    BUSINESS = "business"
    FIRST = "first"


class FareTier(StrEnum):
    """Fare flexibility band within a cabin."""

    SAVER = "saver"
    STANDARD = "standard"
    FLEX = "flex"


class Carrier(BaseModel):
    """An operating airline."""

    code: str = Field(min_length=2, max_length=3)
    name: str


class FlightSegment(BaseModel):
    """A single operated leg of a flight offer."""

    carrier: Carrier
    flight_number: str
    origin_city_id: str
    destination_city_id: str
    departure: datetime
    arrival: datetime
    duration_minutes: int = Field(gt=0)


class FlightOffer(BaseModel):
    """A priced, bookable flight option."""

    offer_id: str
    segments: list[FlightSegment]
    cabin: CabinClass
    fare_tier: FareTier
    price: Money
    seats_available: int = Field(ge=0)
    baggage_kg: int = Field(ge=0)
    refundable: bool

    @property
    def total_duration_minutes(self) -> int:
        """Sum of all segment durations."""
        return sum(segment.duration_minutes for segment in self.segments)


class FlightSearchRequest(BaseModel):
    """Inputs for a one-way flight search between two cities."""

    origin_city_id: str
    destination_city_id: str
    departure_date: date
    cabin: CabinClass = CabinClass.ECONOMY
    max_offers: int = Field(default=4, ge=1, le=8)
