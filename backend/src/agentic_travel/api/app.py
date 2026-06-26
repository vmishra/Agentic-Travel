"""FastAPI application exposing the travel planner over HTTP and AG-UI SSE."""

from __future__ import annotations

import uuid

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from agentic_travel.agents.coordinator import PlanningResult
from agentic_travel.api.agui import plan_event_stream
from agentic_travel.api.dependencies import PlannerFactory, Services, build_services
from agentic_travel.config.settings import Settings, get_settings
from agentic_travel.domain.traveler import TravelerProfile
from agentic_travel.observability.tracer import Tracer

_DEV_ORIGINS = ["http://localhost:3000", "http://127.0.0.1:3000"]


class PlanRequest(BaseModel):
    """A request to plan an itinerary from a free-text message."""

    query: str
    traveler_id: str | None = None


class HealthResponse(BaseModel):
    """Service health and capability report."""

    status: str
    live_models: bool
    missing_config: list[str]


def create_app(settings: Settings | None = None, services: Services | None = None) -> FastAPI:
    """Build the FastAPI app, wiring services and the planner factory."""
    settings = settings or get_settings()
    services = services or build_services()
    factory = PlannerFactory(settings, services)

    app = FastAPI(title="Agentic Travel API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_DEV_ORIGINS,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    def health() -> HealthResponse:
        missing = settings.validate_for_live_models()
        return HealthResponse(status="ok", live_models=not missing, missing_config=missing)

    @app.get("/personas")
    def personas() -> list[TravelerProfile]:
        return services.memory.list_personas()

    @app.post("/plan")
    def plan(request: PlanRequest) -> PlanningResult:
        coordinator = factory.build(Tracer())
        return coordinator.plan_itinerary(request.query, traveler_id=request.traveler_id)

    @app.post("/plan/stream")
    def plan_stream(request: PlanRequest) -> StreamingResponse:
        stream = plan_event_stream(
            factory,
            query=request.query,
            traveler_id=request.traveler_id,
            thread_id=uuid.uuid4().hex,
            run_id=uuid.uuid4().hex,
        )
        return StreamingResponse(stream, media_type="text/event-stream")

    return app


app = create_app()
