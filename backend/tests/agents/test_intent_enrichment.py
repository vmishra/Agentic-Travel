from datetime import date
from decimal import Decimal

from agentic_travel.agents.enrichment import EnrichmentAgent
from agentic_travel.agents.intent import IntentAgent, IntentOut
from agentic_travel.agents.models import BriefExtract, IntentResult, TripIntent
from agentic_travel.domain.money import Currency
from agentic_travel.domain.traveler import BudgetTier, FoodPreference, TravelerProfile
from agentic_travel.llm.client import FakeLlmClient
from agentic_travel.observability.span import SpanKind
from agentic_travel.observability.tracer import Tracer


def _profile() -> TravelerProfile:
    return TravelerProfile(
        traveler_id="tr_arjun",
        display_name="Arjun Mehta",
        home_city_id="city_bom",
        passport_country="IN",
        food_preference=FoodPreference.VEGETARIAN,
        budget_tier=BudgetTier.PREMIUM,
        interests=["history", "food"],
    )


def test_intent_agent_classifies_and_keeps_query() -> None:
    fake = FakeLlmClient(
        objects=[IntentOut(intent=TripIntent.ITINERARY, confidence=0.95, destination_hint="Goa")]
    )
    result = IntentAgent(fake).run("Plan me 3 nights in Goa", model="fast")
    assert result.intent is TripIntent.ITINERARY
    assert result.destination_hint == "Goa"
    assert result.raw_query == "Plan me 3 nights in Goa"


def test_intent_agent_emits_agent_span() -> None:
    fake = FakeLlmClient(objects=[IntentOut(intent=TripIntent.INQUIRY, confidence=0.8)])
    tracer = Tracer()
    IntentAgent(fake, tracer=tracer).run("Tell me about Dubai", model="fast")
    kinds = {(s.name, s.kind) for s in tracer.finished_spans()}
    assert ("intent", SpanKind.AGENT) in kinds


def test_enrichment_merges_profile_defaults() -> None:
    intent_fake = FakeLlmClient(
        objects=[IntentOut(intent=TripIntent.ITINERARY, confidence=0.9, destination_hint="Goa")]
    )
    intent = IntentAgent(intent_fake).run("4 nights in Goa for an anniversary", model="fast")

    enrich_fake = FakeLlmClient(
        objects=[
            BriefExtract(
                destination_query="Goa",
                start_date=date(2026, 12, 5),
                nights=4,
                party_size=2,
                budget_amount=Decimal("80000"),
                budget_currency="INR",
                occasion="anniversary",
                interests=["beaches"],
            )
        ]
    )
    brief = EnrichmentAgent(enrich_fake).run(intent, _profile(), model="fast")

    assert brief.origin_city_id == "city_bom"  # from profile
    assert brief.food_preference is FoodPreference.VEGETARIAN  # from profile
    assert brief.budget_tier is BudgetTier.PREMIUM
    assert brief.nights == 4
    assert brief.party_size == 2
    assert brief.budget is not None
    assert brief.budget.currency is Currency.INR
    assert brief.occasion == "anniversary"
    assert "history" in brief.interests and "beaches" in brief.interests  # merged
    assert brief.clarifications_needed == []


def test_enrichment_flags_missing_slots_without_profile() -> None:
    enrich_fake = FakeLlmClient(objects=[BriefExtract(destination_query="")])
    intent = IntentResult(intent=TripIntent.ITINERARY, confidence=0.5, raw_query="plan a trip")
    brief = EnrichmentAgent(enrich_fake).run(intent, None, model="fast")
    assert "destination" in brief.clarifications_needed
    assert "travel dates or duration" in brief.clarifications_needed
    assert brief.budget_tier is BudgetTier.MID_RANGE  # default w/o profile
