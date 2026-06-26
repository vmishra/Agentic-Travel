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
