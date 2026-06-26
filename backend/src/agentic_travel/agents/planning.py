"""Gather bookable options for a brief into a single planning context.

The specialist data steps (flights, hotels, visa, weather, candidate POIs) are
deterministic service calls. Each is wrapped in a TOOL span so the technical
view shows exactly what was fetched, how long it took, and from where.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import timedelta

from pydantic import BaseModel, Field

from agentic_travel.agents.models import TripBrief
from agentic_travel.domain.traveler import BudgetTier
from agentic_travel.graph.models import POI
from agentic_travel.graph.store import GraphStore
from agentic_travel.observability.span import SpanKind
from agentic_travel.observability.tracer import Tracer
from agentic_travel.services.flights.models import (
    CabinClass,
    FlightOffer,
    FlightSearchRequest,
)
from agentic_travel.services.flights.service import FlightService
from agentic_travel.services.hotels.models import HotelOffer, HotelSearchRequest
from agentic_travel.services.hotels.service import HotelService
from agentic_travel.services.visa.models import VisaRequirement
from agentic_travel.services.visa.service import VisaService
from agentic_travel.services.weather.models import WeatherBrief
from agentic_travel.services.weather.service import WeatherService

_DEFAULT_NIGHTS = 3
_MAX_POIS_PER_CITY = 8

_CABIN_BY_TIER: dict[BudgetTier, CabinClass] = {
    BudgetTier.BUDGET: CabinClass.ECONOMY,
    BudgetTier.MID_RANGE: CabinClass.ECONOMY,
    BudgetTier.PREMIUM: CabinClass.PREMIUM_ECONOMY,
    BudgetTier.LUXURY: CabinClass.BUSINESS,
}


class CityOptions(BaseModel):
    """Bookable options and candidates for a single destination city."""

    city_id: str
    city_name: str
    nights: int
    hotels: list[HotelOffer] = Field(default_factory=list)
    weather: WeatherBrief
    candidate_pois: list[POI] = Field(default_factory=list)


class PlanningContext(BaseModel):
    """Everything the synthesizer needs to compose an itinerary."""

    brief: TripBrief
    origin_city_id: str | None
    destination_city_ids: list[str]
    outbound_flights: list[FlightOffer] = Field(default_factory=list)
    return_flights: list[FlightOffer] = Field(default_factory=list)
    cities: list[CityOptions] = Field(default_factory=list)
    visas: list[VisaRequirement] = Field(default_factory=list)


def _allocate_nights(total: int, num_cities: int) -> list[int]:
    """Split ``total`` nights across cities as evenly as possible (min 1 each)."""
    if num_cities <= 0:
        return []
    base = max(1, total // num_cities)
    allocation = [base] * num_cities
    allocation[0] += max(0, total - base * num_cities)
    return allocation


class OptionsGatherer:
    """Fetches flights, hotels, visa, weather, and POIs for a brief."""

    def __init__(
        self,
        *,
        store: GraphStore,
        flights: FlightService,
        hotels: HotelService,
        visa: VisaService,
        weather: WeatherService,
        tracer: Tracer | None = None,
        max_pois_per_city: int = _MAX_POIS_PER_CITY,
    ) -> None:
        """Wire the gatherer to the data services and graph store."""
        self._store = store
        self._flights = flights
        self._hotels = hotels
        self._visa = visa
        self._weather = weather
        self._tracer = tracer
        self._max_pois = max_pois_per_city

    @contextmanager
    def _tool(self, name: str) -> Iterator[None]:
        if self._tracer is None:
            yield
        else:
            with self._tracer.span(name, SpanKind.TOOL):
                yield

    def gather(self, brief: TripBrief, destination_city_ids: list[str]) -> PlanningContext:
        """Assemble a :class:`PlanningContext` for the brief and destinations."""
        total_nights = brief.nights or _DEFAULT_NIGHTS
        nights_alloc = _allocate_nights(total_nights, len(destination_city_ids))
        month = brief.start_date.month if brief.start_date else 1
        cabin = _CABIN_BY_TIER[brief.budget_tier]

        cities = [
            self._city_options(city_id, nights, month, brief)
            for city_id, nights in zip(destination_city_ids, nights_alloc, strict=True)
        ]
        outbound, inbound = self._flight_options(brief, destination_city_ids, total_nights, cabin)
        visas = self._visa_options(brief, destination_city_ids)

        return PlanningContext(
            brief=brief,
            origin_city_id=brief.origin_city_id,
            destination_city_ids=destination_city_ids,
            outbound_flights=outbound,
            return_flights=inbound,
            cities=cities,
            visas=visas,
        )

    def _city_options(
        self, city_id: str, nights: int, month: int, brief: TripBrief
    ) -> CityOptions:
        city = self._store.get_city(city_id)
        city_name = city.name if city else city_id
        with self._tool(f"hotels:{city_id}"):
            hotels = self._hotels.search(
                HotelSearchRequest(
                    city_id=city_id, nights=nights, budget_tier=brief.budget_tier
                )
            )
        with self._tool(f"weather:{city_id}"):
            weather = self._weather.brief(city_id, month)
        with self._tool(f"pois:{city_id}"):
            pois = self._rank_pois(city_id, brief)
        return CityOptions(
            city_id=city_id,
            city_name=city_name,
            nights=nights,
            hotels=hotels,
            weather=weather,
            candidate_pois=pois,
        )

    def _rank_pois(self, city_id: str, brief: TripBrief) -> list[POI]:
        interests = {i.lower() for i in brief.interests}

        def score(poi: POI) -> tuple[int, float]:
            tags = {t.lower() for t in poi.tags} | {poi.category.value}
            matches = 1 if tags & interests else 0
            return (matches, poi.rating)

        ranked = sorted(self._store.pois_in_city(city_id), key=score, reverse=True)
        return ranked[: self._max_pois]

    def _flight_options(
        self,
        brief: TripBrief,
        destination_city_ids: list[str],
        total_nights: int,
        cabin: CabinClass,
    ) -> tuple[list[FlightOffer], list[FlightOffer]]:
        if not brief.origin_city_id or not destination_city_ids or brief.start_date is None:
            return [], []
        first, last = destination_city_ids[0], destination_city_ids[-1]
        with self._tool(f"flights:{brief.origin_city_id}->{first}"):
            outbound = self._flights.search(
                FlightSearchRequest(
                    origin_city_id=brief.origin_city_id,
                    destination_city_id=first,
                    departure_date=brief.start_date,
                    cabin=cabin,
                )
            )
        return_date = brief.start_date + timedelta(days=total_nights)
        with self._tool(f"flights:{last}->{brief.origin_city_id}"):
            inbound = self._flights.search(
                FlightSearchRequest(
                    origin_city_id=last,
                    destination_city_id=brief.origin_city_id,
                    departure_date=return_date,
                    cabin=cabin,
                )
            )
        return outbound, inbound

    def _visa_options(
        self, brief: TripBrief, destination_city_ids: list[str]
    ) -> list[VisaRequirement]:
        seen: set[str] = set()
        visas: list[VisaRequirement] = []
        for city_id in destination_city_ids:
            city = self._store.get_city(city_id)
            if city is None:
                continue
            country = self._store.get_country(city.country_id)
            if country is None or country.iso_code in seen:
                continue
            seen.add(country.iso_code)
            with self._tool(f"visa:{country.iso_code}"):
                visas.append(self._visa.assess(brief.passport_country, country.iso_code))
        return visas
