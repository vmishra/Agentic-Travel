"""Construction of services and the planner used by the API.

The :class:`PlannerFactory` chooses the live (Gemini) reasoning path when the
required credentials are configured, and the credential-free heuristic path
otherwise — so the API works out of the box and upgrades transparently.
"""

from __future__ import annotations

from dataclasses import dataclass

from agentic_travel.agents.coordinator import Coordinator, ModelConfig
from agentic_travel.agents.heuristic import HeuristicLlmClient, HeuristicSynthesizer
from agentic_travel.agents.synthesizer import (
    LlmSynthesizer,
    SynthesisStrategy,
    SynthesizerAgent,
)
from agentic_travel.config.settings import Settings
from agentic_travel.data.loader import load_default_graph_store
from agentic_travel.graph.store import GraphStore
from agentic_travel.llm.client import GeminiClient, LlmClient
from agentic_travel.observability.tracer import Tracer
from agentic_travel.services.flights.service import FlightService
from agentic_travel.services.hotels.service import HotelService
from agentic_travel.services.memory.service import MemoryService
from agentic_travel.services.visa.service import VisaService
from agentic_travel.services.weather.service import WeatherService


@dataclass(frozen=True)
class Services:
    """The data services and graph store shared across requests."""

    store: GraphStore
    flights: FlightService
    hotels: HotelService
    visa: VisaService
    weather: WeatherService
    memory: MemoryService


def build_services() -> Services:
    """Load every data service from its packaged dataset."""
    return Services(
        store=load_default_graph_store(),
        flights=FlightService.from_default_dataset(),
        hotels=HotelService.from_default_dataset(),
        visa=VisaService.from_default_dataset(),
        weather=WeatherService.from_default_dataset(),
        memory=MemoryService.from_default_dataset(),
    )


class PlannerFactory:
    """Builds a per-request :class:`Coordinator` with a fresh tracer."""

    def __init__(self, settings: Settings, services: Services) -> None:
        """Capture settings and services, and decide the reasoning path."""
        self._settings = settings
        self._services = services
        self._live = not settings.validate_for_live_models()

    @property
    def live_enabled(self) -> bool:
        """True when live Gemini reasoning is configured."""
        return self._live

    def _reasoning(self, tracer: Tracer) -> tuple[LlmClient, SynthesisStrategy, ModelConfig]:
        if self._live:
            llm: LlmClient = GeminiClient.from_settings(self._settings, tracer)
            planner_model = self._settings.gemini_model_planner or ""
            synthesizer: SynthesisStrategy = LlmSynthesizer(
                SynthesizerAgent(llm, tracer=tracer), planner_model
            )
            models = ModelConfig(
                fast=self._settings.gemini_model_fast or "", planner=planner_model
            )
            return llm, synthesizer, models
        return (
            HeuristicLlmClient(),
            HeuristicSynthesizer(self._services.store),
            ModelConfig(fast="heuristic", planner="heuristic"),
        )

    def build(self, tracer: Tracer) -> Coordinator:
        """Construct a coordinator wired to the chosen reasoning path."""
        llm, synthesizer, models = self._reasoning(tracer)
        return Coordinator(
            llm=llm,
            synthesizer=synthesizer,
            store=self._services.store,
            flights=self._services.flights,
            hotels=self._services.hotels,
            visa=self._services.visa,
            weather=self._services.weather,
            memory=self._services.memory,
            models=models,
            tracer=tracer,
        )
