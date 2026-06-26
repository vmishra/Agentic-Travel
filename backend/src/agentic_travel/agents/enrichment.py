"""Query enrichment agent: turns a classified message into a planning brief."""

from __future__ import annotations

from agentic_travel.agents.base import Agent
from agentic_travel.agents.models import BriefExtract, IntentResult, TripBrief
from agentic_travel.domain.money import Currency, Money
from agentic_travel.domain.traveler import BudgetTier, FoodPreference, TravelerProfile

_SYSTEM = """\
Extract structured trip details from the traveler's message. Capture the
destination text, travel dates, number of nights, party size, any stated budget
amount and its currency, the occasion, and interests. Leave a field null/empty
when the message does not state it. Do not invent details."""


class EnrichmentAgent(Agent):
    """Combines extracted slots with the traveler profile into a `TripBrief`."""

    name = "enrichment"

    def run(
        self,
        intent: IntentResult,
        profile: TravelerProfile | None,
        *,
        model: str,
    ) -> TripBrief:
        """Produce an enriched brief, applying profile defaults and gap-flagging."""
        with self._span():
            extract, _ = self._llm.generate_structured(
                model=model,
                system=_SYSTEM,
                prompt=intent.raw_query,
                schema=BriefExtract,
            )
            return self._assemble(intent, extract, profile)

    def _assemble(
        self,
        intent: IntentResult,
        extract: BriefExtract,
        profile: TravelerProfile | None,
    ) -> TripBrief:
        destination = extract.destination_query or (intent.destination_hint or "")
        interests = list(
            dict.fromkeys([*(profile.interests if profile else []), *extract.interests])
        )
        budget = self._resolve_budget(extract)
        clarifications = self._missing(destination, extract)
        return TripBrief(
            intent=intent.intent,
            traveler_id=profile.traveler_id if profile else None,
            passport_country=profile.passport_country if profile else "IN",
            origin_city_id=profile.home_city_id if profile else None,
            destination_query=destination,
            start_date=extract.start_date,
            nights=extract.nights,
            party_size=extract.party_size or 1,
            budget=budget,
            budget_tier=profile.budget_tier if profile else BudgetTier.MID_RANGE,
            food_preference=profile.food_preference if profile else FoodPreference.NONE,
            interests=interests,
            occasion=extract.occasion,
            clarifications_needed=clarifications,
        )

    @staticmethod
    def _resolve_budget(extract: BriefExtract) -> Money | None:
        if extract.budget_amount is None:
            return None
        currency = Currency.INR
        if extract.budget_currency:
            try:
                currency = Currency(extract.budget_currency.upper())
            except ValueError:
                currency = Currency.INR
        return Money(amount=extract.budget_amount, currency=currency)

    @staticmethod
    def _missing(destination: str, extract: BriefExtract) -> list[str]:
        missing: list[str] = []
        if not destination:
            missing.append("destination")
        if extract.nights is None and extract.start_date is None:
            missing.append("travel dates or duration")
        return missing
