import warnings

from agentic_travel.integrations.adk_planner import (
    build_a2a_app,
    build_planner_agent,
    plan_trip,
    reset_factory_for_testing,
)


def setup_function() -> None:
    reset_factory_for_testing()


def test_plan_trip_tool_returns_summary() -> None:
    result = plan_trip("Plan 2 nights in Goa", traveler_id="tr_arjun")
    assert result["valid"] is True
    assert result["days"] >= 1
    assert result["destination_city_ids"] == ["city_goi"]
    assert result["estimated_total_inr"] is not None


def test_plan_trip_requests_clarification_when_underspecified() -> None:
    result = plan_trip("I want to go somewhere nice")
    assert result["title"] is None
    assert result["clarifications_needed"]  # asks for missing details rather than guessing


def test_build_planner_agent_has_tool() -> None:
    agent = build_planner_agent()
    assert agent.name == "agentic_travel_planner"
    assert len(agent.tools) == 1


def test_build_a2a_app_constructs() -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # ADK A2A support is flagged experimental
        app = build_a2a_app(port=8123)
    assert app is not None
