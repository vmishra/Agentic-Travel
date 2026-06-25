"""MCP server exposing flight search as a tool.

Run standalone for ADK / MCP clients::

    python -m agentic_travel.mcp_servers.flights            # stdio transport
    python -m agentic_travel.mcp_servers.flights --http     # streamable-http
"""

from __future__ import annotations

import sys
from datetime import date

from mcp.server.fastmcp import FastMCP

from agentic_travel.services.flights.models import (
    CabinClass,
    FlightOffer,
    FlightSearchRequest,
)
from agentic_travel.services.flights.service import FlightService

mcp = FastMCP("agentic-travel-flights")
_service = FlightService.from_default_dataset()


@mcp.tool()
def search_flights(
    origin_city_id: str,
    destination_city_id: str,
    departure_date: str,
    cabin: CabinClass = CabinClass.ECONOMY,
    max_offers: int = 4,
) -> list[FlightOffer]:
    """Search one-way flights between two cities on a date.

    Args:
        origin_city_id: Graph city id to depart from (e.g. ``city_bom``).
        destination_city_id: Graph city id to arrive at (e.g. ``city_goi``).
        departure_date: Departure date in ISO format (``YYYY-MM-DD``).
        cabin: Cabin class to price.
        max_offers: Maximum number of fare options to return.

    Returns:
        Bookable flight offers across fare tiers, cheapest first.

    """
    request = FlightSearchRequest(
        origin_city_id=origin_city_id,
        destination_city_id=destination_city_id,
        departure_date=date.fromisoformat(departure_date),
        cabin=cabin,
        max_offers=max_offers,
    )
    return _service.search(request)


def main() -> None:
    """Run the flight MCP server over stdio or streamable HTTP."""
    if "--http" in sys.argv:
        mcp.run(transport="streamable-http")
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
