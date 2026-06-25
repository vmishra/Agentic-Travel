"""Typed nodes and edges for the point-of-interest graph.

The model is shaped to map cleanly onto a property graph (e.g. Spanner Graph):
nodes carry a stable string ``id`` and edges reference nodes by id.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

from agentic_travel.domain.geo import GeoPoint
from agentic_travel.domain.money import Money


class NodeKind(StrEnum):
    """Discriminator for graph nodes."""

    REGION = "region"
    COUNTRY = "country"
    CITY = "city"
    POI = "poi"


class EdgeKind(StrEnum):
    """Discriminator for graph edges."""

    CONTAINS = "contains"
    NEAR = "near"
    CONNECTED_BY = "connected_by"


class TransportMode(StrEnum):
    """Mode of travel along a CONNECTED_BY edge."""

    WALK = "walk"
    CAR = "car"
    TRANSIT = "transit"
    FLIGHT = "flight"


class POICategory(StrEnum):
    """High-level classification of a point of interest."""

    LANDMARK = "landmark"
    MUSEUM = "museum"
    NATURE = "nature"
    BEACH = "beach"
    RELIGIOUS = "religious"
    MARKET = "market"
    ENTERTAINMENT = "entertainment"
    ADVENTURE = "adventure"


class OpeningHours(BaseModel):
    """Daily opening window for a POI. ``days`` uses 0=Monday .. 6=Sunday."""

    opens: str = Field(pattern=r"^\d{2}:\d{2}$")
    closes: str = Field(pattern=r"^\d{2}:\d{2}$")
    days: list[int] = Field(default_factory=lambda: [0, 1, 2, 3, 4, 5, 6])


class Region(BaseModel):
    """A multi-country region (e.g. Southeast Asia)."""

    id: str
    name: str


class Country(BaseModel):
    """A country contained in a region."""

    id: str
    name: str
    region_id: str
    iso_code: str = Field(min_length=2, max_length=2)


class City(BaseModel):
    """A city contained in a country."""

    id: str
    name: str
    country_id: str
    location: GeoPoint
    timezone: str


class POI(BaseModel):
    """A point of interest, usually within a city."""

    id: str
    name: str
    city_id: str | None
    location: GeoPoint
    category: POICategory
    typical_visit_minutes: int = Field(gt=0)
    ticket_price: Money | None = None
    rating: float = Field(ge=0.0, le=5.0)
    opening_hours: OpeningHours | None = None
    tags: list[str] = Field(default_factory=list)


class Edge(BaseModel):
    """A directed relationship between two nodes referenced by id."""

    source_id: str
    target_id: str
    kind: EdgeKind
    distance_km: float | None = None
    mode: TransportMode | None = None
    duration_minutes: int | None = None
