"""Mock hotel search over a curated property dataset."""

from __future__ import annotations

import hashlib
from importlib import resources
from pathlib import Path

from pydantic import BaseModel

from agentic_travel.domain.money import Money
from agentic_travel.services.hotels.models import (
    Hotel,
    HotelOffer,
    HotelSearchRequest,
    RoomType,
)


class _HotelDataset(BaseModel):
    hotels: list[Hotel]


def _seed(*parts: str) -> int:
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
    return int(digest[:8], 16)


class HotelService:
    """Searches a curated hotel dataset and prices stays by night count."""

    def __init__(self, dataset: _HotelDataset) -> None:
        """Group hotels by city for fast lookup."""
        self._by_city: dict[str, list[Hotel]] = {}
        for hotel in dataset.hotels:
            self._by_city.setdefault(hotel.city_id, []).append(hotel)

    @classmethod
    def from_default_dataset(cls) -> HotelService:
        """Load the packaged hotel dataset."""
        resource = resources.files("agentic_travel.data") / "hotels.json"
        dataset = _HotelDataset.model_validate_json(
            Path(str(resource)).read_text(encoding="utf-8")
        )
        return cls(dataset)

    def search(self, request: HotelSearchRequest) -> list[HotelOffer]:
        """Return matching hotels as priced offers, best-rated first."""
        candidates = self._by_city.get(request.city_id, [])
        if request.budget_tier is not None:
            candidates = [h for h in candidates if h.budget_tier is request.budget_tier]
        if request.required_amenities:
            required = set(request.required_amenities)
            candidates = [h for h in candidates if required <= set(h.amenities)]

        ranked = sorted(candidates, key=lambda h: h.guest_rating, reverse=True)
        offers: list[HotelOffer] = []
        for hotel in ranked[: request.max_offers]:
            seed = _seed(hotel.hotel_id, str(request.nights))
            total = Money(
                amount=hotel.nightly_rate.amount * request.nights,
                currency=hotel.nightly_rate.currency,
            )
            offers.append(
                HotelOffer(
                    offer_id=f"ht_{seed:08x}",
                    hotel=hotel,
                    room_type=RoomType.STANDARD,
                    nights=request.nights,
                    total_price=total,
                    rooms_available=1 + (seed % 6),
                    free_cancellation=hotel.budget_tier.value != "budget",
                )
            )
        return offers
