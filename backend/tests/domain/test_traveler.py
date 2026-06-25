from agentic_travel.domain.traveler import (
    BudgetTier,
    FoodPreference,
    TravelerProfile,
)


def test_traveler_profile_round_trip() -> None:
    profile = TravelerProfile(
        traveler_id="tr_arjun",
        display_name="Arjun Mehta",
        home_city_id="city_del",
        passport_country="IN",
        food_preference=FoodPreference.VEGETARIAN,
        budget_tier=BudgetTier.PREMIUM,
        loyalty_programs=["Marriott Bonvoy"],
        visited_city_ids=["city_dxb"],
        interests=["history", "food"],
    )
    restored = TravelerProfile.model_validate_json(profile.model_dump_json())
    assert restored == profile
    assert restored.food_preference is FoodPreference.VEGETARIAN
