"""Deterministic mock flight search over a curated route dataset."""

from __future__ import annotations

import hashlib
from datetime import datetime, time, timedelta
from decimal import Decimal
from importlib import resources
from pathlib import Path

from pydantic import BaseModel

from agentic_travel.domain.fx import to_inr
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
_LAYOVER_MINUTES = 120


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
        """Index routes by (origin, destination) and collect hub candidates."""
        self._routes: dict[tuple[str, str], _Route] = {
            (route.origin_city_id, route.destination_city_id): route
            for route in dataset.routes
        }
        self._hubs: list[str] = sorted({city for pair in self._routes for city in pair})

    @classmethod
    def from_default_dataset(cls) -> FlightService:
        """Load the packaged flight route dataset."""
        resource = resources.files("agentic_travel.data") / "flight_routes.json"
        dataset = _RouteDataset.model_validate_json(
            Path(str(resource)).read_text(encoding="utf-8")
        )
        return cls(dataset)

    def search(self, request: FlightSearchRequest) -> list[FlightOffer]:
        """Return offers for the route: direct if available, else one-stop."""
        direct = self._direct(request)
        if direct:
            return direct
        return self._connecting(request)

    def _direct(self, request: FlightSearchRequest) -> list[FlightOffer]:
        route = self._routes.get((request.origin_city_id, request.destination_city_id))
        if route is None:
            return []
        date_iso = request.departure_date.isoformat()
        offers: list[FlightOffer] = []
        for index, tier in enumerate(_TIER_ORDER[: request.max_offers]):
            seed = _seed(
                request.origin_city_id, request.destination_city_id, date_iso, tier.value,
                request.cabin.value,
            )
            departure = datetime.combine(
                request.departure_date, time(hour=6 + (seed % 14), minute=(seed % 4) * 15)
            )
            segment, _ = self._leg(
                route, request.origin_city_id, request.destination_city_id, departure, tier,
                request.cabin, index, date_iso,
            )
            price = (
                route.base_saver_fare * _TIER_MULTIPLIER[tier] * _CABIN_MULTIPLIER[request.cabin]
            ).quantize(Decimal("1"))
            offers.append(
                FlightOffer(
                    offer_id=f"fl_{seed:08x}",
                    segments=[segment],
                    cabin=request.cabin,
                    fare_tier=tier,
                    price=Money(amount=price, currency=route.currency),
                    seats_available=3 + (seed % 8),
                    baggage_kg=15 if tier is FareTier.SAVER else 25,
                    refundable=tier is FareTier.FLEX,
                )
            )
        offers.sort(key=lambda offer: offer.price.amount)
        return offers

    def _connecting(self, request: FlightSearchRequest) -> list[FlightOffer]:
        for hub in self._hubs:
            if hub in (request.origin_city_id, request.destination_city_id):
                continue
            first = self._routes.get((request.origin_city_id, hub))
            second = self._routes.get((hub, request.destination_city_id))
            if first is not None and second is not None:
                return self._connecting_offers(request, first, second, hub)
        return []

    def _connecting_offers(
        self, request: FlightSearchRequest, first: _Route, second: _Route, hub: str
    ) -> list[FlightOffer]:
        date_iso = request.departure_date.isoformat()
        offers: list[FlightOffer] = []
        for index, tier in enumerate(_TIER_ORDER[: request.max_offers]):
            seed = _seed(request.origin_city_id, hub, date_iso, tier.value, request.cabin.value)
            depart1 = datetime.combine(
                request.departure_date, time(hour=6 + (seed % 10), minute=(seed % 4) * 15)
            )
            seg1, inr1 = self._leg(
                first, request.origin_city_id, hub, depart1, tier, request.cabin, index, date_iso
            )
            depart2 = seg1.arrival + timedelta(minutes=_LAYOVER_MINUTES)
            seg2, inr2 = self._leg(
                second, hub, request.destination_city_id, depart2, tier, request.cabin,
                index + 1, date_iso,
            )
            offers.append(
                FlightOffer(
                    offer_id=f"fc_{seed:08x}",
                    segments=[seg1, seg2],
                    cabin=request.cabin,
                    fare_tier=tier,
                    price=Money(amount=inr1 + inr2, currency=Currency.INR),
                    seats_available=2 + (seed % 6),
                    baggage_kg=15 if tier is FareTier.SAVER else 25,
                    refundable=tier is FareTier.FLEX,
                )
            )
        offers.sort(key=lambda offer: offer.price.amount)
        return offers

    def _leg(
        self,
        route: _Route,
        origin: str,
        destination: str,
        departure: datetime,
        tier: FareTier,
        cabin: CabinClass,
        carrier_index: int,
        date_iso: str,
    ) -> tuple[FlightSegment, Decimal]:
        """Build one operated leg and its fare converted to INR."""
        carrier = route.carriers[carrier_index % len(route.carriers)]
        seed = _seed(origin, destination, date_iso, tier.value, cabin.value)
        raw = (
            route.base_saver_fare * _TIER_MULTIPLIER[tier] * _CABIN_MULTIPLIER[cabin]
        ).quantize(Decimal("1"))
        segment = FlightSegment(
            carrier=carrier,
            flight_number=f"{carrier.code} {100 + (seed % 900)}",
            origin_city_id=origin,
            destination_city_id=destination,
            departure=departure,
            arrival=departure + timedelta(minutes=route.duration_minutes),
            duration_minutes=route.duration_minutes,
        )
        return segment, to_inr(Money(amount=raw, currency=route.currency)).amount
