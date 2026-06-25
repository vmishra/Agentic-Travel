"""MCP server exposing hotel search as a tool.

Run standalone::

    python -m agentic_travel.mcp_servers.hotels            # stdio transport
    python -m agentic_travel.mcp_servers.hotels --http     # streamable-http
"""

from __future__ import annotations

import sys

from mcp.server.fastmcp import FastMCP

from agentic_travel.domain.traveler import BudgetTier
from agentic_travel.services.hotels.models import (
    HotelAmenity,
    HotelOffer,
    HotelSearchRequest,
)
from agentic_travel.services.hotels.service import HotelService

mcp = FastMCP("agentic-travel-hotels")
_service = HotelService.from_default_dataset()


@mcp.tool()
def search_hotels(
    city_id: str,
    nights: int,
    budget_tier: BudgetTier | None = None,
    required_amenities: list[HotelAmenity] | None = None,
    max_offers: int = 4,
) -> list[HotelOffer]:
    """Search bookable hotels in a city for a number of nights.

    Args:
        city_id: Graph city id to search within (e.g. ``city_goi``).
        nights: Number of nights to price the stay for.
        budget_tier: Optional budget band to filter to.
        required_amenities: Amenities every returned hotel must offer.
        max_offers: Maximum number of hotels to return.

    Returns:
        Priced hotel offers, highest guest rating first.

    """
    request = HotelSearchRequest(
        city_id=city_id,
        nights=nights,
        budget_tier=budget_tier,
        required_amenities=required_amenities or [],
        max_offers=max_offers,
    )
    return _service.search(request)


def main() -> None:
    """Run the hotel MCP server over stdio or streamable HTTP."""
    if "--http" in sys.argv:
        mcp.run(transport="streamable-http")
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
