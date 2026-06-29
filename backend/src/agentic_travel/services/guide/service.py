"""City practical guidance: getting around and month-relevant events."""

from __future__ import annotations

from importlib import resources
from pathlib import Path

from pydantic import BaseModel

from agentic_travel.services.guide.models import CityGuide, GuideEvent


class _GuideDataset(BaseModel):
    cities: list[CityGuide]


class GuideService:
    """Serves getting-around notes and events for a city."""

    def __init__(self, dataset: _GuideDataset) -> None:
        """Index guides by city id."""
        self._guides: dict[str, CityGuide] = {g.city_id: g for g in dataset.cities}

    @classmethod
    def from_default_dataset(cls) -> GuideService:
        """Load the packaged city guide dataset."""
        resource = resources.files("agentic_travel.data") / "city_guides.json"
        dataset = _GuideDataset.model_validate_json(
            Path(str(resource)).read_text(encoding="utf-8")
        )
        return cls(dataset)

    def getting_around(self, city_id: str) -> str | None:
        """Return the getting-around note for a city, if known."""
        guide = self._guides.get(city_id)
        return guide.getting_around if guide and guide.getting_around else None

    def events_for(self, city_id: str, month: int) -> list[GuideEvent]:
        """Return events for a city in a given month, plus year-round ones."""
        guide = self._guides.get(city_id)
        if guide is None:
            return []
        return [e for e in guide.events if e.month == month or e.month == 0]
