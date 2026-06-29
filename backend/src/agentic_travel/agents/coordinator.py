"""The coordinator: orchestrates the bookable-itinerary hero flow.

intent -> personalization -> enrichment -> destination resolution -> parallel
option gathering -> synthesis -> validate-and-repair loop. Every step is traced,
so a full run reconstructs the live agent graph with per-step latency and cost.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from pydantic import BaseModel, Field

from agentic_travel.agents.destination import DestinationResolver
from agentic_travel.agents.enrichment import EnrichmentAgent
from agentic_travel.agents.intent import IntentAgent
from agentic_travel.agents.models import (
    BriefExtract,
    ConversationState,
    IntentResult,
    TripBrief,
)
from agentic_travel.agents.planning import OptionsGatherer, PlanningContext
from agentic_travel.agents.synthesizer import ItineraryAssembler, SynthesisStrategy
from agentic_travel.domain.money import Money
from agentic_travel.domain.traveler import BudgetTier, FoodPreference, TravelerProfile
from agentic_travel.graph.store import GraphStore
from agentic_travel.itinerary.models import Itinerary
from agentic_travel.itinerary.validation import ValidationReport, validate_itinerary
from agentic_travel.llm.client import LlmClient
from agentic_travel.observability.span import SpanKind
from agentic_travel.observability.tracer import Tracer
from agentic_travel.services.dining.service import DiningService
from agentic_travel.services.flights.service import FlightService
from agentic_travel.services.guide.service import GuideService
from agentic_travel.services.hotels.service import HotelService
from agentic_travel.services.memory.service import MemoryService
from agentic_travel.services.visa.service import VisaService
from agentic_travel.services.weather.service import WeatherService


class ModelConfig(BaseModel):
    """The model ids used for each tier of reasoning."""

    fast: str
    planner: str


class PlanningResult(BaseModel):
    """The outcome of a planning run."""

    brief: TripBrief
    itinerary: Itinerary | None = None
    validation: ValidationReport = Field(default_factory=ValidationReport)
    resolved_city_ids: list[str] = Field(default_factory=list)
    attempts: int = 0
    conversation: ConversationState = Field(default_factory=ConversationState)


class Coordinator:
    """Runs the end-to-end itinerary pipeline with a critic repair loop."""

    def __init__(
        self,
        *,
        llm: LlmClient,
        synthesizer: SynthesisStrategy,
        store: GraphStore,
        flights: FlightService,
        hotels: HotelService,
        visa: VisaService,
        weather: WeatherService,
        memory: MemoryService,
        models: ModelConfig,
        dining: DiningService | None = None,
        guide: GuideService | None = None,
        tracer: Tracer | None = None,
        max_repairs: int = 2,
    ) -> None:
        """Construct the coordinator from a model client, synthesis strategy, and services."""
        self._intent = IntentAgent(llm, tracer=tracer)
        self._enrich = EnrichmentAgent(llm, tracer=tracer)
        self._resolver = DestinationResolver(store)
        self._gatherer = OptionsGatherer(
            store=store, flights=flights, hotels=hotels, visa=visa, weather=weather, tracer=tracer
        )
        self._synthesizer = synthesizer
        self._assembler = ItineraryAssembler(store, dining, guide)
        self._store = store
        self._memory = memory
        self._models = models
        self._tracer = tracer
        self._max_repairs = max_repairs

    @contextmanager
    def _span(self, name: str, kind: SpanKind = SpanKind.AGENT) -> Iterator[None]:
        if self._tracer is None:
            yield
        else:
            with self._tracer.span(name, kind):
                yield

    def plan_itinerary(
        self,
        query: str,
        *,
        traveler_id: str | None = None,
        state: ConversationState | None = None,
    ) -> PlanningResult:
        """Plan a bookable itinerary, accumulating slots across conversation turns."""
        state = state.model_copy(deep=True) if state else ConversationState()
        with self._span("coordinator"):
            intent = self._intent.run(query, model=self._models.fast)
            profile = self._memory.get_profile(traveler_id) if traveler_id else None
            with self._span("enrichment"):
                extract = self._enrich.extract(query, model=self._models.fast)
            self._merge(state, extract)
            brief = self._build_brief(intent, state, profile)

            if brief.clarifications_needed:
                return PlanningResult(brief=brief, conversation=state)

            with self._span("specialists"):
                context = self._gatherer.gather(brief, state.destination_city_ids)

            itinerary, report, attempts = self._synthesize_with_repair(context)
            return PlanningResult(
                brief=brief,
                itinerary=itinerary,
                validation=report,
                resolved_city_ids=state.destination_city_ids,
                attempts=attempts,
                conversation=state,
            )

    def _merge(self, state: ConversationState, extract: BriefExtract) -> None:
        """Fold a message's extracted slots into the accumulated state."""
        cities = self._resolver.resolve(extract.destination_query)
        if cities:
            state.destination_city_ids = cities
        if extract.start_date is not None:
            state.start_date = extract.start_date
        if extract.nights is not None:
            state.nights = extract.nights
        if extract.party_size is not None:
            state.party_size = extract.party_size
        budget = self._enrich.resolve_budget(extract)
        if budget is not None:
            state.budget = budget
        if extract.occasion:
            state.occasion = extract.occasion
        if extract.interests:
            state.interests = list(dict.fromkeys([*state.interests, *extract.interests]))

    def _build_brief(
        self,
        intent: IntentResult,
        state: ConversationState,
        profile: TravelerProfile | None,
    ) -> TripBrief:
        missing: list[str] = []
        if not state.destination_city_ids:
            covered = ", ".join(sorted(c.name for c in self._store.all_cities()))
            missing.append(f"a destination I currently cover ({covered})")
        if state.nights is None and state.start_date is None:
            missing.append("travel dates or duration")
        interests = list(
            dict.fromkeys([*(profile.interests if profile else []), *state.interests])
        )
        return TripBrief(
            intent=intent.intent,
            traveler_id=profile.traveler_id if profile else None,
            passport_country=profile.passport_country if profile else "IN",
            origin_city_id=profile.home_city_id if profile else None,
            destination_query=", ".join(state.destination_city_ids),
            start_date=state.start_date,
            nights=state.nights,
            party_size=state.party_size or 1,
            budget=state.budget,
            budget_tier=profile.budget_tier if profile else BudgetTier.MID_RANGE,
            food_preference=profile.food_preference if profile else FoodPreference.NONE,
            interests=interests,
            occasion=state.occasion,
            clarifications_needed=missing,
        )

    def _synthesize_with_repair(
        self, context: PlanningContext
    ) -> tuple[Itinerary, ValidationReport, int]:
        feedback: list[str] | None = None
        itinerary: Itinerary | None = None
        report = ValidationReport()
        max_attempts = self._max_repairs + 1
        for attempt in range(1, max_attempts + 1):
            plan = self._synthesizer.propose(context, feedback=feedback)
            itinerary = self._assembler.assemble(
                plan, context, itinerary_id=f"itin_{attempt}"
            )
            report = self._critique(itinerary, context.brief.budget)
            if report.is_valid:
                return itinerary, report, attempt
            feedback = [issue.message for issue in report.errors]
        assert itinerary is not None  # loop runs at least once
        return itinerary, report, max_attempts

    def _critique(self, itinerary: Itinerary, budget: Money | None) -> ValidationReport:
        with self._span("critic"):
            return validate_itinerary(itinerary, self._store, budget=budget)
