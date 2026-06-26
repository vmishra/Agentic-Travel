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
from agentic_travel.agents.models import TripBrief
from agentic_travel.agents.planning import OptionsGatherer, PlanningContext
from agentic_travel.agents.synthesizer import ItineraryAssembler, SynthesisStrategy
from agentic_travel.domain.money import Money
from agentic_travel.graph.store import GraphStore
from agentic_travel.itinerary.models import Itinerary
from agentic_travel.itinerary.validation import (
    IssueSeverity,
    ValidationIssue,
    ValidationReport,
    validate_itinerary,
)
from agentic_travel.llm.client import LlmClient
from agentic_travel.observability.span import SpanKind
from agentic_travel.observability.tracer import Tracer
from agentic_travel.services.flights.service import FlightService
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
        self._assembler = ItineraryAssembler(store)
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

    def plan_itinerary(self, query: str, *, traveler_id: str | None = None) -> PlanningResult:
        """Plan a bookable itinerary for a free-text request."""
        with self._span("coordinator"):
            intent = self._intent.run(query, model=self._models.fast)
            profile = self._memory.get_profile(traveler_id) if traveler_id else None
            brief = self._enrich.run(intent, profile, model=self._models.fast)

            if brief.clarifications_needed:
                return PlanningResult(brief=brief)

            city_ids = self._resolver.resolve(brief.destination_query)
            if not city_ids:
                return PlanningResult(
                    brief=brief,
                    validation=ValidationReport(
                        issues=[
                            ValidationIssue(
                                severity=IssueSeverity.ERROR,
                                code="unresolved_destination",
                                message=(
                                    f"Could not match '{brief.destination_query}' to a known "
                                    "destination."
                                ),
                            )
                        ]
                    ),
                )

            with self._span("specialists"):
                context = self._gatherer.gather(brief, city_ids)

            itinerary, report, attempts = self._synthesize_with_repair(context)
            return PlanningResult(
                brief=brief,
                itinerary=itinerary,
                validation=report,
                resolved_city_ids=city_ids,
                attempts=attempts,
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
