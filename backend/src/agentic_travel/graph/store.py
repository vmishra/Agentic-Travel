"""Storage and traversal for the POI graph.

``GraphStore`` defines the read interface the rest of the system depends on.
``InMemoryGraphStore`` is the local JSON-backed implementation; a future
``SpannerGraphStore`` can implement the same interface without changing callers.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from pydantic import BaseModel

from agentic_travel.graph.models import (
    POI,
    City,
    Country,
    Edge,
    EdgeKind,
    Region,
    TransportMode,
)


class GraphData(BaseModel):
    """Serializable container for an entire graph."""

    regions: list[Region]
    countries: list[Country]
    cities: list[City]
    pois: list[POI]
    edges: list[Edge]


class GraphStore(ABC):
    """Read interface over the POI graph.

    The methods below form the contract every backing store must satisfy.
    Single-node lookups return ``None`` when the id is unknown; collection
    queries return an empty list.
    """

    @abstractmethod
    def get_region(self, region_id: str) -> Region | None:
        """Return the region with ``region_id``, or ``None`` if absent."""

    @abstractmethod
    def get_country(self, country_id: str) -> Country | None:
        """Return the country with ``country_id``, or ``None`` if absent."""

    @abstractmethod
    def get_city(self, city_id: str) -> City | None:
        """Return the city with ``city_id``, or ``None`` if absent."""

    @abstractmethod
    def get_poi(self, poi_id: str) -> POI | None:
        """Return the POI with ``poi_id``, or ``None`` if absent."""

    @abstractmethod
    def countries_in_region(self, region_id: str) -> list[Country]:
        """Return all countries belonging to ``region_id``."""

    @abstractmethod
    def cities_in_country(self, country_id: str) -> list[City]:
        """Return all cities belonging to ``country_id``."""

    @abstractmethod
    def pois_in_city(self, city_id: str) -> list[POI]:
        """Return all POIs located in ``city_id``."""

    @abstractmethod
    def connections_from(
        self, node_id: str, mode: TransportMode | None = None
    ) -> list[Edge]:
        """Return CONNECTED_BY edges out of ``node_id``, optionally by ``mode``."""


class InMemoryGraphStore(GraphStore):
    """Graph store backed by in-memory dictionaries built from ``GraphData``."""

    def __init__(self, data: GraphData) -> None:
        """Index ``data`` by node id for constant-time lookups."""
        self._regions = {r.id: r for r in data.regions}
        self._countries = {c.id: c for c in data.countries}
        self._cities = {c.id: c for c in data.cities}
        self._pois = {p.id: p for p in data.pois}
        self._edges = list(data.edges)

    def get_region(self, region_id: str) -> Region | None:  # noqa: D102 — see GraphStore
        return self._regions.get(region_id)

    def get_country(self, country_id: str) -> Country | None:  # noqa: D102
        return self._countries.get(country_id)

    def get_city(self, city_id: str) -> City | None:  # noqa: D102
        return self._cities.get(city_id)

    def get_poi(self, poi_id: str) -> POI | None:  # noqa: D102
        return self._pois.get(poi_id)

    def countries_in_region(self, region_id: str) -> list[Country]:  # noqa: D102
        return [c for c in self._countries.values() if c.region_id == region_id]

    def cities_in_country(self, country_id: str) -> list[City]:  # noqa: D102
        return [c for c in self._cities.values() if c.country_id == country_id]

    def pois_in_city(self, city_id: str) -> list[POI]:  # noqa: D102
        return [p for p in self._pois.values() if p.city_id == city_id]

    def connections_from(  # noqa: D102
        self, node_id: str, mode: TransportMode | None = None
    ) -> list[Edge]:
        return [
            edge
            for edge in self._edges
            if edge.source_id == node_id
            and edge.kind is EdgeKind.CONNECTED_BY
            and (mode is None or edge.mode is mode)
        ]


def load_graph_data(path: Path) -> GraphData:
    """Load a :class:`GraphData` document from a JSON file."""
    return GraphData.model_validate_json(Path(path).read_text(encoding="utf-8"))
