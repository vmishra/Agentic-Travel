"""MCP server exposing seasonal weather briefs as a tool.

Run standalone::

    python -m agentic_travel.mcp_servers.weather            # stdio transport
    python -m agentic_travel.mcp_servers.weather --http     # streamable-http
"""

from __future__ import annotations

import sys

from mcp.server.fastmcp import FastMCP

from agentic_travel.services.weather.models import WeatherBrief
from agentic_travel.services.weather.service import WeatherService

mcp = FastMCP("agentic-travel-weather")
_service = WeatherService.from_default_dataset()


@mcp.tool()
def get_weather_brief(city_id: str, month: int) -> WeatherBrief:
    """Return the seasonal climate brief for a city in a given month.

    Args:
        city_id: Graph city id (e.g. ``city_goi``).
        month: Month of travel as an integer (1=January .. 12=December).

    Returns:
        A climate brief with season, temperatures, rain probability, and a
        recommendation flag; a neutral fallback when data is unavailable.

    """
    return _service.brief(city_id, month)


def main() -> None:
    """Run the weather MCP server over stdio or streamable HTTP."""
    if "--http" in sys.argv:
        mcp.run(transport="streamable-http")
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
