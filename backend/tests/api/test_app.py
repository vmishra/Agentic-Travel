from fastapi.testclient import TestClient

from agentic_travel.api.app import create_app
from agentic_travel.config.settings import Settings


def _client() -> TestClient:
    # Explicit empty settings -> credential-free heuristic path.
    return TestClient(create_app(settings=Settings(_env_file=None)))  # type: ignore[call-arg]


def test_health_reports_offline_without_key() -> None:
    response = _client().get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["live_models"] is False
    assert "GEMINI_API_KEY" in body["missing_config"]


def test_personas_endpoint() -> None:
    response = _client().get("/personas")
    assert response.status_code == 200
    personas = response.json()
    assert len(personas) >= 3
    assert any(p["traveler_id"] == "tr_arjun" for p in personas)


def test_plan_endpoint_produces_valid_itinerary() -> None:
    response = _client().post(
        "/plan", json={"query": "Plan 2 nights in Goa", "traveler_id": "tr_arjun"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["itinerary"] is not None
    assert body["validation"]["issues"] == [] or all(
        i["severity"] != "error" for i in body["validation"]["issues"]
    )
    assert body["resolved_city_ids"] == ["city_goi"]


def test_conversation_accumulates_across_turns() -> None:
    client = _client()
    session = "sess-test-1"
    first = client.post(
        "/plan",
        json={"query": "I'd like to visit Goa", "traveler_id": "tr_arjun", "session_id": session},
    ).json()
    assert first["itinerary"] is None
    assert "travel dates or duration" in first["brief"]["clarifications_needed"]

    second = client.post(
        "/plan",
        json={"query": "make it 3 nights", "traveler_id": "tr_arjun", "session_id": session},
    ).json()
    assert second["itinerary"] is not None  # destination carried over from turn 1
    assert second["resolved_city_ids"] == ["city_goi"]


def test_introspect_describes_the_agent_graph() -> None:
    response = _client().get("/introspect")
    assert response.status_code == 200
    arch = response.json()

    # Credential-free path reports the heuristic reasoning models.
    assert arch["live"] is False
    assert arch["model_fast"] == "heuristic"
    assert arch["model_planner"] == "heuristic"

    root = arch["root"]
    assert root["id"] == "coordinator"
    assert root["kind"] == "coordinator"

    children = {c["id"] for c in root["children"]}
    assert {"intent", "enrichment", "specialists", "synthesizer", "critic"} <= children

    specialists = next(c for c in root["children"] if c["id"] == "specialists")
    tools = {c["id"] for c in specialists["children"]}
    assert {"flights", "hotels", "visa", "weather", "pois"} <= tools

    # Every node that maps to a runtime step declares a matching prefix, so the
    # live highlight can find it from a STEP_STARTED event.
    assert specialists["children"][0]["step_match"]  # e.g. ["flights:"]
    assert {p["key"] for p in arch["protocols"]} == {"adk", "a2a", "mcp", "agui", "gemini"}


def test_plan_stream_emits_agui_events() -> None:
    response = _client().post(
        "/plan/stream", json={"query": "Plan 2 nights in Goa", "traveler_id": "tr_arjun"}
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    text = response.text
    assert "RUN_STARTED" in text
    assert "STEP_STARTED" in text
    assert "trace.span" in text  # custom metrics event
    assert "STATE_SNAPSHOT" in text
    assert "RUN_FINISHED" in text
