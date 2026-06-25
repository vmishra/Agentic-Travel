from pathlib import Path

import pytest

from agentic_travel.config.settings import Settings


@pytest.fixture(autouse=True)
def _isolate_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Run each test from an empty directory so no real ``.env`` is picked up."""
    monkeypatch.chdir(tmp_path)


def test_settings_read_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("GEMINI_MODEL_PLANNER", "model-planner")
    monkeypatch.setenv("API_PORT", "9001")
    settings = Settings()
    assert settings.gemini_api_key == "test-key"
    assert settings.gemini_model_planner == "model-planner"
    assert settings.api_port == 9001
    assert settings.app_env == "development"  # default


def test_validate_for_live_models_reports_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in ("GEMINI_API_KEY", "GEMINI_MODEL_PLANNER", "GEMINI_MODEL_FAST"):
        monkeypatch.delenv(var, raising=False)
    missing = Settings().validate_for_live_models()
    assert "GEMINI_API_KEY" in missing
    assert "GEMINI_MODEL_PLANNER" in missing
    assert "GEMINI_MODEL_FAST" in missing


def test_validate_for_live_models_clean_when_present(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "k")
    monkeypatch.setenv("GEMINI_MODEL_PLANNER", "p")
    monkeypatch.setenv("GEMINI_MODEL_FAST", "f")
    assert Settings().validate_for_live_models() == []
