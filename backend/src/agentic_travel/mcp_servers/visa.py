"""MCP server exposing visa requirement assessment as a tool.

Run standalone::

    python -m agentic_travel.mcp_servers.visa            # stdio transport
    python -m agentic_travel.mcp_servers.visa --http     # streamable-http
"""

from __future__ import annotations

import sys

from mcp.server.fastmcp import FastMCP

from agentic_travel.services.visa.models import VisaRequirement
from agentic_travel.services.visa.service import VisaService

mcp = FastMCP("agentic-travel-visa")
_service = VisaService.from_default_dataset()


@mcp.tool()
def assess_visa(passport_country: str, destination_country: str) -> VisaRequirement:
    """Assess the entry requirement for a passport/destination pair.

    Args:
        passport_country: Traveler's passport country (ISO 3166 alpha-2, e.g. ``IN``).
        destination_country: Destination country (ISO 3166 alpha-2, e.g. ``AE``).

    Returns:
        The visa/entry requirement, defaulting conservatively when unknown.

    """
    return _service.assess(passport_country, destination_country)


def main() -> None:
    """Run the visa MCP server over stdio or streamable HTTP."""
    if "--http" in sys.argv:
        mcp.run(transport="streamable-http")
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
