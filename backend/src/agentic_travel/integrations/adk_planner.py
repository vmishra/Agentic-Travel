"""Expose the travel planner through Google's ADK and the A2A protocol.

This is the boundary integration described in ADR-0001: the planning core is
wrapped as an ADK agent whose tool runs the full coordinator, and `to_a2a`
publishes it as an A2A server (with an agent card) so other agents can call it.

Run the A2A server::

    python -m agentic_travel.integrations.adk_planner
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from agentic_travel.api.dependencies import PlannerFactory, build_services
from agentic_travel.config.settings import Settings, get_settings
from agentic_travel.observability.tracer import Tracer

if TYPE_CHECKING:
    from google.adk.agents import LlmAgent

_DEFAULT_FAST_MODEL = "gemini-3.5-flash"
_AGENT_INSTRUCTION = (
    "You help travelers plan bookable trips. For any planning request, call the "
    "plan_trip tool with the user's message and (if known) their traveler id, then "
    "present the returned itinerary clearly, noting flights, hotels, visa, and budget."
)

_factory: PlannerFactory | None = None


def _get_factory() -> PlannerFactory:
    global _factory
    if _factory is None:
        _factory = PlannerFactory(get_settings(), build_services())
    return _factory


def plan_trip(query: str, traveler_id: str = "") -> dict[str, Any]:
    """Plan a bookable itinerary for a free-text travel request.

    Args:
        query: The traveler's request, e.g. "5 nights in Goa for a couple".
        traveler_id: Optional known traveler id for personalization (may be empty).

    Returns:
        A compact summary of the planned itinerary and its validation outcome.

    """
    coordinator = _get_factory().build(Tracer())
    result = coordinator.plan_itinerary(query, traveler_id=traveler_id or None)
    itinerary = result.itinerary
    return {
        "title": itinerary.title if itinerary else None,
        "valid": result.validation.is_valid,
        "days": len(itinerary.days) if itinerary else 0,
        "estimated_total_inr": str(itinerary.estimated_total.amount) if itinerary else None,
        "destination_city_ids": result.resolved_city_ids,
        "clarifications_needed": result.brief.clarifications_needed,
    }


def build_planner_agent(settings: Settings | None = None) -> LlmAgent:
    """Build the ADK agent that wraps the planner as a tool."""
    from google.adk.agents import LlmAgent

    settings = settings or get_settings()
    model = settings.gemini_model_fast or _DEFAULT_FAST_MODEL
    return LlmAgent(
        model=model,
        name="agentic_travel_planner",
        description="Plans bookable, personalized travel itineraries.",
        instruction=_AGENT_INSTRUCTION,
        tools=[plan_trip],
    )


def build_a2a_app(port: int = 8001, settings: Settings | None = None) -> Any:
    """Publish the planner agent as an A2A server application."""
    from google.adk.a2a.utils.agent_to_a2a import to_a2a

    return to_a2a(build_planner_agent(settings), port=port)


def main() -> None:
    """Serve the planner as an A2A server."""
    import uvicorn

    settings = get_settings()
    port = 8001
    uvicorn.run(build_a2a_app(port=port, settings=settings), host=settings.api_host, port=port)


# Module-level agent for ADK tooling discovery (`adk web`, `adk run`).
root_agent_factory = build_planner_agent


if __name__ == "__main__":
    main()


def reset_factory_for_testing() -> None:
    """Reset the cached factory (used by tests to isolate state)."""
    global _factory
    _factory = None
