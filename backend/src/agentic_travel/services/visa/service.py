"""Visa requirement lookups over a curated rules dataset."""

from __future__ import annotations

from importlib import resources
from pathlib import Path

from pydantic import BaseModel

from agentic_travel.services.visa.models import VisaCategory, VisaRequirement


class _RulesDataset(BaseModel):
    rules: list[VisaRequirement]


class VisaService:
    """Resolves entry requirements, defaulting conservatively when unknown."""

    def __init__(self, dataset: _RulesDataset) -> None:
        """Index rules by (passport, destination)."""
        self._rules: dict[tuple[str, str], VisaRequirement] = {
            (rule.passport_country, rule.destination_country): rule
            for rule in dataset.rules
        }

    @classmethod
    def from_default_dataset(cls) -> VisaService:
        """Load the packaged visa rules dataset."""
        resource = resources.files("agentic_travel.data") / "visa_rules.json"
        dataset = _RulesDataset.model_validate_json(
            Path(str(resource)).read_text(encoding="utf-8")
        )
        return cls(dataset)

    def assess(self, passport_country: str, destination_country: str) -> VisaRequirement:
        """Return the entry requirement for the given passport and destination."""
        if passport_country == destination_country:
            return VisaRequirement(
                passport_country=passport_country,
                destination_country=destination_country,
                category=VisaCategory.NOT_REQUIRED_DOMESTIC,
                processing_days=0,
                fee=None,
                max_stay_days=0,
                notes="Domestic travel; no visa required.",
            )
        known = self._rules.get((passport_country, destination_country))
        if known is not None:
            return known
        return VisaRequirement(
            passport_country=passport_country,
            destination_country=destination_country,
            category=VisaCategory.EMBASSY,
            processing_days=15,
            fee=None,
            max_stay_days=0,
            notes=(
                "No cached rule for this route; confirm requirements with the "
                "destination embassy or consulate before booking."
            ),
        )
