from agentic_travel.domain.traveler import BudgetTier, FoodPreference
from agentic_travel.services.memory.service import MemoryService


def _service() -> MemoryService:
    return MemoryService.from_default_dataset()


def test_get_profile_returns_rich_persona() -> None:
    profile = _service().get_profile("tr_arjun")
    assert profile is not None
    assert profile.food_preference is FoodPreference.VEGETARIAN
    assert profile.budget_tier is BudgetTier.PREMIUM
    assert "Marriott Bonvoy" in profile.loyalty_programs


def test_list_personas_has_at_least_three() -> None:
    assert len(_service().list_personas()) >= 3


def test_unknown_profile_is_none() -> None:
    assert _service().get_profile("tr_nobody") is None


def test_session_memory_is_mutable_in_memory() -> None:
    service = _service()
    session = service.get_session("tr_meera")
    assert "yoga retreat Goa" in session.recent_searches
    service.remember_search("tr_meera", "Colombo food tour")
    assert "Colombo food tour" in service.get_session("tr_meera").recent_searches


def test_unknown_session_is_empty() -> None:
    session = _service().get_session("tr_nobody")
    assert session.recent_searches == []
    assert session.current_trip_notes == []
