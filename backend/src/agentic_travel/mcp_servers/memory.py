"""MCP server exposing traveler profiles and session memory as tools.

Run standalone::

    python -m agentic_travel.mcp_servers.memory            # stdio transport
    python -m agentic_travel.mcp_servers.memory --http     # streamable-http
"""

from __future__ import annotations

import sys

from mcp.server.fastmcp import FastMCP

from agentic_travel.domain.traveler import TravelerProfile
from agentic_travel.services.memory.models import SessionMemory
from agentic_travel.services.memory.service import MemoryService

mcp = FastMCP("agentic-travel-memory")
_service = MemoryService.from_default_dataset()


@mcp.tool()
def get_traveler_profile(traveler_id: str) -> TravelerProfile | None:
    """Return a traveler's long-term profile by id, or null if unknown."""
    return _service.get_profile(traveler_id)


@mcp.tool()
def list_personas() -> list[TravelerProfile]:
    """Return all known traveler profiles."""
    return _service.list_personas()


@mcp.tool()
def get_session_memory(traveler_id: str) -> SessionMemory:
    """Return a traveler's short-term session memory (empty if none yet)."""
    return _service.get_session(traveler_id)


def main() -> None:
    """Run the memory MCP server over stdio or streamable HTTP."""
    if "--http" in sys.argv:
        mcp.run(transport="streamable-http")
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
