"""Deterministic itinerary validation — the anti-hallucination guardrail.

Every referenced point of interest is cross-checked against the graph store, and
time feasibility, opening hours, pace, budget, and day coverage are verified with
plain (non-LLM) logic so a plan can be rejected and re-planned when infeasible.
"""

from __future__ import annotations

from datetime import time
from enum import StrEnum

from pydantic import BaseModel, Field

from agentic_travel.domain.money import Money
from agentic_travel.graph.models import OpeningHours
from agentic_travel.graph.store import GraphStore
from agentic_travel.itinerary.models import Activity, DayPlan, Itinerary

_DEFAULT_MAX_ACTIVITIES_PER_DAY = 6


class IssueSeverity(StrEnum):
    """Severity of a validation issue."""

    ERROR = "error"
    WARNING = "warning"


class ValidationIssue(BaseModel):
    """A single problem found while validating an itinerary."""

    severity: IssueSeverity
    code: str
    message: str
    day_index: int | None = None
    poi_id: str | None = None


class ValidationReport(BaseModel):
    """The outcome of validating an itinerary."""

    issues: list[ValidationIssue] = Field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        """True when there are no error-severity issues."""
        return not any(issue.severity is IssueSeverity.ERROR for issue in self.issues)

    @property
    def errors(self) -> list[ValidationIssue]:
        """The error-severity issues only."""
        return [i for i in self.issues if i.severity is IssueSeverity.ERROR]


def _minutes(value: time) -> int:
    return value.hour * 60 + value.minute


def _parse_hhmm(value: str) -> int:
    hours, minutes = value.split(":")
    return int(hours) * 60 + int(minutes)


def _within_opening_hours(activity: Activity, hours: OpeningHours, weekday: int) -> bool:
    if weekday not in hours.days:
        return False
    opens = _parse_hhmm(hours.opens)
    closes = _parse_hhmm(hours.closes)
    return _minutes(activity.start) >= opens and _minutes(activity.end) <= closes


def _check_day(
    day: DayPlan, store: GraphStore, max_activities_per_day: int
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []

    if len(day.activities) > max_activities_per_day:
        issues.append(
            ValidationIssue(
                severity=IssueSeverity.WARNING,
                code="packed_day",
                message=(
                    f"Day {day.day_index} has {len(day.activities)} activities, "
                    f"above the comfortable pace of {max_activities_per_day}."
                ),
                day_index=day.day_index,
            )
        )

    for activity in day.activities:
        if not activity.has_valid_times:
            issues.append(
                ValidationIssue(
                    severity=IssueSeverity.ERROR,
                    code="invalid_times",
                    message=(
                        f"'{activity.name}' ends at or before it starts "
                        f"({activity.start}-{activity.end})."
                    ),
                    day_index=day.day_index,
                    poi_id=activity.poi_id,
                )
            )
        poi = store.get_poi(activity.poi_id)
        if poi is None:
            issues.append(
                ValidationIssue(
                    severity=IssueSeverity.ERROR,
                    code="unknown_poi",
                    message=f"Activity references unknown point of interest '{activity.poi_id}'.",
                    day_index=day.day_index,
                    poi_id=activity.poi_id,
                )
            )
            continue
        if poi.city_id is not None and poi.city_id != day.city_id:
            issues.append(
                ValidationIssue(
                    severity=IssueSeverity.WARNING,
                    code="poi_city_mismatch",
                    message=(
                        f"'{poi.name}' is in {poi.city_id} but scheduled on a "
                        f"{day.city_id} day."
                    ),
                    day_index=day.day_index,
                    poi_id=activity.poi_id,
                )
            )
        if poi.opening_hours is not None and not _within_opening_hours(
            activity, poi.opening_hours, day.date.weekday()
        ):
            issues.append(
                ValidationIssue(
                    severity=IssueSeverity.WARNING,
                    code="outside_opening_hours",
                    message=(
                        f"'{poi.name}' is scheduled outside its opening hours "
                        f"({poi.opening_hours.opens}-{poi.opening_hours.closes})."
                    ),
                    day_index=day.day_index,
                    poi_id=activity.poi_id,
                )
            )

    issues.extend(_check_overlaps(day))
    return issues


def _check_overlaps(day: DayPlan) -> list[ValidationIssue]:
    ordered = sorted(day.activities, key=lambda a: _minutes(a.start))
    issues: list[ValidationIssue] = []
    for earlier, later in zip(ordered, ordered[1:], strict=False):
        if _minutes(later.start) < _minutes(earlier.end):
            issues.append(
                ValidationIssue(
                    severity=IssueSeverity.ERROR,
                    code="overlapping_activities",
                    message=(
                        f"'{earlier.name}' and '{later.name}' overlap on day "
                        f"{day.day_index}."
                    ),
                    day_index=day.day_index,
                )
            )
    return issues


def validate_itinerary(
    itinerary: Itinerary,
    store: GraphStore,
    *,
    budget: Money | None = None,
    max_activities_per_day: int = _DEFAULT_MAX_ACTIVITIES_PER_DAY,
) -> ValidationReport:
    """Validate an itinerary for grounding, feasibility, pace, and budget."""
    issues: list[ValidationIssue] = []

    if len(itinerary.days) != itinerary.day_span:
        issues.append(
            ValidationIssue(
                severity=IssueSeverity.WARNING,
                code="day_count_mismatch",
                message=(
                    f"Itinerary spans {itinerary.day_span} days but has "
                    f"{len(itinerary.days)} day plans."
                ),
            )
        )

    for day in itinerary.days:
        issues.extend(_check_day(day, store, max_activities_per_day))

    if budget is not None and budget.currency is itinerary.estimated_total.currency:
        if itinerary.estimated_total.amount > budget.amount:
            issues.append(
                ValidationIssue(
                    severity=IssueSeverity.ERROR,
                    code="over_budget",
                    message=(
                        f"Estimated total {itinerary.estimated_total.amount} "
                        f"{itinerary.estimated_total.currency} exceeds the budget of "
                        f"{budget.amount} {budget.currency}."
                    ),
                )
            )

    return ValidationReport(issues=issues)
