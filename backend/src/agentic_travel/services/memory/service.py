"""Traveler long-term profiles and short-term session memory."""

from __future__ import annotations

from importlib import resources
from pathlib import Path

from pydantic import BaseModel

from agentic_travel.domain.traveler import TravelerProfile
from agentic_travel.services.memory.models import SessionMemory


class _PersonaRecord(BaseModel):
    profile: TravelerProfile
    session: SessionMemory


class _PersonaDataset(BaseModel):
    personas: list[_PersonaRecord]


class MemoryService:
    """Serves persona profiles and mutable in-memory session state."""

    def __init__(self, dataset: _PersonaDataset) -> None:
        """Index profiles and seed session memory from the dataset."""
        self._profiles: dict[str, TravelerProfile] = {}
        self._sessions: dict[str, SessionMemory] = {}
        for record in dataset.personas:
            self._profiles[record.profile.traveler_id] = record.profile
            self._sessions[record.session.traveler_id] = record.session.model_copy(deep=True)

    @classmethod
    def from_default_dataset(cls) -> MemoryService:
        """Load the packaged personas dataset."""
        resource = resources.files("agentic_travel.data") / "personas.json"
        dataset = _PersonaDataset.model_validate_json(
            Path(str(resource)).read_text(encoding="utf-8")
        )
        return cls(dataset)

    def get_profile(self, traveler_id: str) -> TravelerProfile | None:
        """Return the long-term profile for a traveler, or ``None``."""
        return self._profiles.get(traveler_id)

    def list_personas(self) -> list[TravelerProfile]:
        """Return all known traveler profiles."""
        return list(self._profiles.values())

    def get_session(self, traveler_id: str) -> SessionMemory:
        """Return short-term session memory, creating an empty one if needed."""
        return self._sessions.setdefault(
            traveler_id, SessionMemory(traveler_id=traveler_id)
        )

    def remember_search(self, traveler_id: str, query: str) -> None:
        """Append a search query to the traveler's short-term memory."""
        self.get_session(traveler_id).recent_searches.append(query)
