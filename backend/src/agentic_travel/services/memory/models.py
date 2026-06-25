"""Short-term session memory model."""

from __future__ import annotations

from pydantic import BaseModel, Field


class SessionMemory(BaseModel):
    """Short-term, per-session memory for a traveler."""

    traveler_id: str
    recent_searches: list[str] = Field(default_factory=list)
    current_trip_notes: list[str] = Field(default_factory=list)
