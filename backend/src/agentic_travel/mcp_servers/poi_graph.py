"""MCP server exposing point-of-interest graph traversal as tools.

Run standalone::

    python -m agentic_travel.mcp_servers.poi_graph            # stdio transport
    python -m agentic_travel.mcp_servers.poi_graph --http     # streamable-http
"""

from __future__ import annotations

import sys

from mcp.server.fastmcp import FastMCP

from agentic_travel.data.loader import load_default_graph_store
from agentic_travel.graph.models import POI, City, Edge, TransportMode

mcp = FastMCP("agentic-travel-poi-graph")
_store = load_default_graph_store()


@mcp.tool()
def get_city(city_id: str) -> City | None:
    """Return a city by id, or null if it does not exist."""
    return _store.get_city(city_id)


@mcp.tool()
def cities_in_country(country_id: str) -> list[City]:
    """Return all cities contained in the given country id."""
    return _store.cities_in_country(country_id)


@mcp.tool()
def pois_in_city(city_id: str) -> list[POI]:
    """Return all points of interest located in the given city id."""
    return _store.pois_in_city(city_id)


@mcp.tool()
def flight_connections(city_id: str) -> list[Edge]:
    """Return cities reachable by flight from the given city id."""
    return _store.connections_from(city_id, mode=TransportMode.FLIGHT)


def main() -> None:
    """Run the POI graph MCP server over stdio or streamable HTTP."""
    if "--http" in sys.argv:
        mcp.run(transport="streamable-http")
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
