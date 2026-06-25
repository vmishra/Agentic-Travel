"""Models describing visa/entry requirements."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

from agentic_travel.domain.money import Money


class VisaCategory(StrEnum):
    """Type of entry permission required."""

    VISA_FREE = "visa_free"
    VISA_ON_ARRIVAL = "visa_on_arrival"
    E_VISA = "e_visa"
    EMBASSY = "embassy"
    NOT_REQUIRED_DOMESTIC = "not_required_domestic"


class VisaRequirement(BaseModel):
    """The entry requirement for a passport/destination pair."""

    passport_country: str = Field(min_length=2, max_length=2)
    destination_country: str = Field(min_length=2, max_length=2)
    category: VisaCategory
    processing_days: int = Field(ge=0)
    fee: Money | None = None
    max_stay_days: int = Field(ge=0)
    notes: str
