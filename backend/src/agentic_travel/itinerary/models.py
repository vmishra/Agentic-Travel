"""Models describing a bookable, day-by-day travel itinerary.

An :class:`Itinerary` is self-contained: it embeds the selected flights, hotels,
and visa assessments alongside the day-by-day plan, so it can be validated and
rendered without re-querying the source services.
"""

from __future__ import annotations

from datetime import date, time

from pydantic import BaseModel, Field

from agentic_travel.domain.money import Money
from agentic_travel.services.flights.models import FlightOffer
from agentic_travel.services.hotels.models import HotelOffer
from agentic_travel.services.visa.models import VisaRequirement


def _minutes(value: time) -> int:
    """Return minutes since midnight for a wall-clock time."""
    return value.hour * 60 + value.minute


class Activity(BaseModel):
    """A single scheduled visit to a point of interest within a day."""

    poi_id: str
    name: str
    start: time
    end: time
    estimated_cost: Money | None = None
    notes: str = ""

    @property
    def duration_minutes(self) -> int:
        """Scheduled duration in minutes (negative if end precedes start)."""
        return _minutes(self.end) - _minutes(self.start)

    @property
    def has_valid_times(self) -> bool:
        """True when the activity ends strictly after it starts."""
        return _minutes(self.end) > _minutes(self.start)


class DayPlan(BaseModel):
    """The ordered set of activities for a single day in one city."""

    day_index: int = Field(ge=1)
    date: date
    city_id: str
    activities: list[Activity] = Field(default_factory=list)
    notes: str = ""


class Itinerary(BaseModel):
    """A complete, bookable itinerary across one or more destinations."""

    itinerary_id: str
    title: str
    traveler_id: str | None = None
    party_size: int = Field(ge=1)
    origin_city_id: str
    destination_city_ids: list[str]
    start_date: date
    end_date: date
    flights: list[FlightOffer] = Field(default_factory=list)
    hotels: list[HotelOffer] = Field(default_factory=list)
    visa: list[VisaRequirement] = Field(default_factory=list)
    days: list[DayPlan] = Field(default_factory=list)
    estimated_total: Money
    summary: str = ""

    @property
    def nights(self) -> int:
        """Number of nights between the start and end dates."""
        return (self.end_date - self.start_date).days

    @property
    def day_span(self) -> int:
        """Inclusive number of calendar days the trip covers."""
        return (self.end_date - self.start_date).days + 1
