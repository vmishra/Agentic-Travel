from agentic_travel.domain.traveler import BudgetTier, FoodPreference
from agentic_travel.services.dining.models import Meal
from agentic_travel.services.dining.service import DiningService


def _service() -> DiningService:
    return DiningService.from_default_dataset()


def test_recommend_returns_restaurant_for_meal() -> None:
    pick = _service().recommend("city_goi", meal=Meal.DINNER)
    assert pick is not None
    assert pick.city_id == "city_goi"
    assert Meal.DINNER in pick.meals


def test_vegetarian_preference_is_respected() -> None:
    pick = _service().recommend(
        "city_bom", meal=Meal.DINNER, food_preference=FoodPreference.VEGETARIAN
    )
    assert pick is not None
    assert {"vegetarian", "vegan"} & set(pick.dietary)


def test_halal_preference_is_respected() -> None:
    pick = _service().recommend(
        "city_dxb", meal=Meal.DINNER, food_preference=FoodPreference.HALAL
    )
    assert pick is not None
    assert "halal" in pick.dietary


def test_exclude_ids_avoids_repeats() -> None:
    service = _service()
    first = service.recommend("city_tyo", meal=Meal.DINNER, budget_tier=BudgetTier.LUXURY)
    assert first is not None
    second = service.recommend(
        "city_tyo", meal=Meal.DINNER, budget_tier=BudgetTier.LUXURY, exclude_ids={first.id}
    )
    assert second is None or second.id != first.id


def test_unknown_city_returns_none() -> None:
    assert _service().recommend("city_none", meal=Meal.LUNCH) is None
