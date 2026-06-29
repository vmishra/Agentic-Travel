"""Restaurant recommendations filtered by diet, meal, and budget."""

from __future__ import annotations

from collections.abc import Iterable
from importlib import resources
from pathlib import Path

from pydantic import BaseModel

from agentic_travel.domain.traveler import BudgetTier, FoodPreference
from agentic_travel.services.dining.models import Meal, Restaurant

_TIER_ORDER: list[BudgetTier] = [
    BudgetTier.BUDGET,
    BudgetTier.MID_RANGE,
    BudgetTier.PREMIUM,
    BudgetTier.LUXURY,
]


class _DiningDataset(BaseModel):
    restaurants: list[Restaurant]


def _satisfies(restaurant: Restaurant, preference: FoodPreference) -> bool:
    tags = set(restaurant.dietary)
    if preference is FoodPreference.NONE:
        return True
    if preference is FoodPreference.VEGETARIAN or preference is FoodPreference.JAIN:
        return "vegetarian" in tags or "vegan" in tags
    if preference is FoodPreference.VEGAN:
        return "vegan" in tags
    if preference is FoodPreference.HALAL:
        return "halal" in tags
    return True


class DiningService:
    """Recommends restaurants honouring diet, meal, and budget tier."""

    def __init__(self, dataset: _DiningDataset) -> None:
        """Group restaurants by city."""
        self._by_city: dict[str, list[Restaurant]] = {}
        for restaurant in dataset.restaurants:
            self._by_city.setdefault(restaurant.city_id, []).append(restaurant)

    @classmethod
    def from_default_dataset(cls) -> DiningService:
        """Load the packaged dining dataset."""
        resource = resources.files("agentic_travel.data") / "dining.json"
        dataset = _DiningDataset.model_validate_json(
            Path(str(resource)).read_text(encoding="utf-8")
        )
        return cls(dataset)

    def recommend(
        self,
        city_id: str,
        *,
        meal: Meal,
        food_preference: FoodPreference = FoodPreference.NONE,
        budget_tier: BudgetTier = BudgetTier.MID_RANGE,
        exclude_ids: Iterable[str] = (),
    ) -> Restaurant | None:
        """Pick the best restaurant for a meal: diet-safe, near budget, top-rated."""
        excluded = set(exclude_ids)
        target = _TIER_ORDER.index(budget_tier)
        candidates = [
            r
            for r in self._by_city.get(city_id, [])
            if r.id not in excluded
            and meal in r.meals
            and _satisfies(r, food_preference)
        ]
        candidates.sort(
            key=lambda r: (abs(_TIER_ORDER.index(r.price_tier) - target), -r.rating)
        )
        return candidates[0] if candidates else None
