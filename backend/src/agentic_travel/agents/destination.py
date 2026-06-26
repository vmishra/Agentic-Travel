"""Resolve free-text destinations to concrete graph cities."""

from __future__ import annotations

from agentic_travel.graph.store import GraphStore


class DestinationResolver:
    """Maps a destination phrase to graph city ids by name matching.

    A country name expands to all of its cities; city names match directly.
    Matching is deterministic so the result is reproducible and testable.
    """

    def __init__(self, store: GraphStore) -> None:
        """Store the graph used for name resolution."""
        self._store = store

    def resolve(self, query: str) -> list[str]:
        """Return graph city ids referenced by ``query`` (order-preserving, unique)."""
        text = query.lower()
        matched: list[str] = []

        for country in self._store.all_countries():
            if country.name.lower() in text:
                for city in self._store.cities_in_country(country.id):
                    if city.id not in matched:
                        matched.append(city.id)

        for city in self._store.all_cities():
            if city.name.lower() in text and city.id not in matched:
                matched.append(city.id)

        return matched
