"""Request and response models for hotel search."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

from agentic_travel.domain.geo import GeoPoint
from agentic_travel.domain.money import Money
from agentic_travel.domain.traveler import BudgetTier


class RoomType(StrEnum):
    """Bookable room category."""

    STANDARD = "standard"
    DELUXE = "deluxe"
    SUITE = "suite"


class HotelAmenity(StrEnum):
    """Amenity offered by a hotel."""

    WIFI = "wifi"
    POOL = "pool"
    BREAKFAST = "breakfast"
    GYM = "gym"
    SPA = "spa"
    AIRPORT_SHUTTLE = "airport_shuttle"


class Hotel(BaseModel):
    """A hotel property."""

    hotel_id: str
    name: str
    city_id: str
    brand: str
    location: GeoPoint
    star_rating: int = Field(ge=1, le=5)
    guest_rating: float = Field(ge=0.0, le=10.0)
    review_count: int = Field(ge=0)
    amenities: list[HotelAmenity] = Field(default_factory=list)
    budget_tier: BudgetTier
    nightly_rate: Money


class HotelOffer(BaseModel):
    """A priced, bookable stay at a hotel."""

    offer_id: str
    hotel: Hotel
    room_type: RoomType
    nights: int = Field(gt=0)
    total_price: Money
    rooms_available: int = Field(ge=0)
    free_cancellation: bool


class HotelSearchRequest(BaseModel):
    """Inputs for a hotel search within a city."""

    city_id: str
    nights: int = Field(gt=0)
    budget_tier: BudgetTier | None = None
    required_amenities: list[HotelAmenity] = Field(default_factory=list)
    max_offers: int = Field(default=4, ge=1, le=10)
