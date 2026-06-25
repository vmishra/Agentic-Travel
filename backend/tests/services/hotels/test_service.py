from agentic_travel.domain.traveler import BudgetTier
from agentic_travel.services.hotels.models import (
    HotelAmenity,
    HotelSearchRequest,
)
from agentic_travel.services.hotels.service import HotelService


def _service() -> HotelService:
    return HotelService.from_default_dataset()


def test_search_returns_city_hotels_sorted_by_rating() -> None:
    service = _service()
    offers = service.search(HotelSearchRequest(city_id="city_bom", nights=3))
    assert offers
    ratings = [o.hotel.guest_rating for o in offers]
    assert ratings == sorted(ratings, reverse=True)
    assert all(o.hotel.city_id == "city_bom" for o in offers)


def test_total_price_scales_with_nights() -> None:
    service = _service()
    offers = service.search(HotelSearchRequest(city_id="city_goi", nights=2, max_offers=1))
    offer = offers[0]
    assert offer.total_price.amount == offer.hotel.nightly_rate.amount * 2


def test_budget_tier_filter() -> None:
    service = _service()
    offers = service.search(
        HotelSearchRequest(city_id="city_bom", nights=1, budget_tier=BudgetTier.MID_RANGE)
    )
    assert all(o.hotel.budget_tier is BudgetTier.MID_RANGE for o in offers)


def test_amenity_filter() -> None:
    service = _service()
    offers = service.search(
        HotelSearchRequest(
            city_id="city_dxb", nights=1, required_amenities=[HotelAmenity.SPA]
        )
    )
    assert offers
    assert all(HotelAmenity.SPA in o.hotel.amenities for o in offers)


def test_unknown_city_returns_empty() -> None:
    service = _service()
    assert service.search(HotelSearchRequest(city_id="city_none", nights=1)) == []
