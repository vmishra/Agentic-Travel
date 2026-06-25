"""Deterministic mock flight search over a curated route dataset."""

from __future__ import annotations

import hashlib
from datetime import datetime, time, timedelta
from decimal import Decimal
from importlib import resources
from pathlib import Path

from pydantic import BaseModel

from agentic_travel.domain.money import Currency, Money
from agentic_travel.services.flights.models import (
    CabinClass,
    Carrier,
    FareTier,
    FlightOffer,
    FlightSearchRequest,
    FlightSegment,
)

# Fare multipliers relative to the route's saver base fare.
_TIER_MULTIPLIER: dict[FareTier, Decimal] = {
    FareTier.SAVER: Decimal("1.00"),
    FareTier.STANDARD: Decimal("1.35"),
    FareTier.FLEX: Decimal("1.80"),
}
_CABIN_MULTIPLIER: dict[CabinClass, Decimal] = {
    CabinClass.ECONOMY: Decimal("1.0"),
    CabinClass.PREMIUM_ECONOMY: Decimal("1.6"),
    CabinClass.BUSINESS: Decimal("2.8"),
    CabinClass.FIRST: Decimal("4.5"),
}
_TIER_ORDER: tuple[FareTier, ...] = (FareTier.SAVER, FareTier.STANDARD, FareTier.FLEX)


class _Route(BaseModel):
    origin_city_id: str
    destination_city_id: str
    currency: Currency
    base_saver_fare: Decimal
    duration_minutes: int
    carriers: list[Carrier]


class _RouteDataset(BaseModel):
    routes: list[_Route]


def _seed(*parts: str) -> int:
    """Return a stable integer seed derived from the given parts."""
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
    return int(digest[:8], 16)


class FlightService:
    """Searches a curated route dataset and synthesizes realistic offers."""

    def __init__(self, dataset: _RouteDataset) -> None:
        """Index routes by (origin, destination)."""
        self._routes: dict[tuple[str, str], _Route] = {
            (route.origin_city_id, route.destination_city_id): route
            for route in dataset.routes
        }

    @classmethod
    def from_default_dataset(cls) -> FlightService:
        """Load the packaged flight route dataset."""
        resource = resources.files("agentic_travel.data") / "flight_routes.json"
        dataset = _RouteDataset.model_validate_json(
            Path(str(resource)).read_text(encoding="utf-8")
        )
        return cls(dataset)

    def search(self, request: FlightSearchRequest) -> list[FlightOffer]:
        """Return tiered offers for the route, cheapest first; empty if unknown."""
        route = self._routes.get(
            (request.origin_city_id, request.destination_city_id)
        )
        if route is None:
            return []

        offers: list[FlightOffer] = []
        for index, tier in enumerate(_TIER_ORDER[: request.max_offers]):
            carrier = route.carriers[index % len(route.carriers)]
            seed = _seed(
                request.origin_city_id,
                request.destination_city_id,
                request.departure_date.isoformat(),
                tier.value,
                request.cabin.value,
            )
            depart_hour = 6 + (seed % 14)  # between 06:00 and 19:00
            departure = datetime.combine(
                request.departure_date, time(hour=depart_hour, minute=(seed % 4) * 15)
            )
            arrival = departure + timedelta(minutes=route.duration_minutes)
            flight_number = f"{carrier.code} {100 + (seed % 900)}"
            price_amount = (
                route.base_saver_fare
                * _TIER_MULTIPLIER[tier]
                * _CABIN_MULTIPLIER[request.cabin]
            ).quantize(Decimal("1"))
            offers.append(
                FlightOffer(
                    offer_id=f"fl_{seed:08x}",
                    segments=[
                        FlightSegment(
                            carrier=carrier,
                            flight_number=flight_number,
                            origin_city_id=request.origin_city_id,
                            destination_city_id=request.destination_city_id,
                            departure=departure,
                            arrival=arrival,
                            duration_minutes=route.duration_minutes,
                        )
                    ],
                    cabin=request.cabin,
                    fare_tier=tier,
                    price=Money(amount=price_amount, currency=route.currency),
                    seats_available=3 + (seed % 8),
                    baggage_kg=15 if tier is FareTier.SAVER else 25,
                    refundable=tier is FareTier.FLEX,
                )
            )
        offers.sort(key=lambda offer: offer.price.amount)
        return offers
