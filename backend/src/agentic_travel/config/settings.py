"""Environment-driven settings for Agentic Travel.

Model identifiers are intentionally not hardcoded: they are read from the
environment and validated against the active credential at startup, so the
project never assumes a model version a given key may not expose.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class MissingConfigError(RuntimeError):
    """Raised when configuration required for an operation is absent."""


class Settings(BaseSettings):
    """Runtime configuration sourced from environment variables / ``.env``."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Gemini / Generative AI
    gemini_api_key: str | None = None
    gemini_model_planner: str | None = None
    gemini_model_fast: str | None = None
    gemini_model_live: str | None = None
    gemini_image_model: str | None = None

    # Google Maps Platform
    google_maps_api_key: str | None = None

    # Vertex AI / Google Cloud
    google_genai_use_vertexai: bool = False
    google_cloud_project: str | None = None
    google_cloud_location: str = "us-central1"

    # Runtime
    app_env: str = "development"
    api_host: str = "127.0.0.1"
    api_port: int = 8000

    def validate_for_live_models(self) -> list[str]:
        """Return the names of variables required for live model calls but unset.

        An empty list means the configuration is ready for live Gemini calls.
        This method never raises; callers decide how to react to a degraded setup.
        """
        required = {
            "GEMINI_API_KEY": self.gemini_api_key,
            "GEMINI_MODEL_PLANNER": self.gemini_model_planner,
            "GEMINI_MODEL_FAST": self.gemini_model_fast,
        }
        return [name for name, value in required.items() if not value]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide cached settings instance."""
    return Settings()
