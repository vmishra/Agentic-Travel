"""In-memory tests for the MCP servers via FastMCP's call_tool path.

These exercise the real MCP registration, schema generation, and execution
without standing up a transport.
"""

from types import ModuleType
from typing import Any

from agentic_travel.mcp_servers import (
    flights,
    hotels,
    memory,
    poi_graph,
    visa,
    weather,
)


async def _call(server: ModuleType, name: str, args: dict[str, Any]) -> Any:
    # FastMCP wraps scalar/list returns under "result"; a model return is the
    # structured dict itself.
    _content, structured = await server.mcp.call_tool(name, args)
    return structured.get("result", structured)


async def test_flights_server_searches() -> None:
    result = await _call(
        flights,
        "search_flights",
        {
            "origin_city_id": "city_bom",
            "destination_city_id": "city_goi",
            "departure_date": "2026-09-12",
        },
    )
    assert len(result) == 3
    assert result[0]["fare_tier"] == "saver"
    assert result[0]["price"]["currency"] == "INR"


async def test_hotels_server_searches() -> None:
    result = await _call(hotels, "search_hotels", {"city_id": "city_bom", "nights": 2})
    assert result
    assert all(o["hotel"]["city_id"] == "city_bom" for o in result)


async def test_visa_server_assesses() -> None:
    result = await _call(
        visa, "assess_visa", {"passport_country": "IN", "destination_country": "LK"}
    )
    assert result["category"] == "e_visa"


async def test_weather_server_brief() -> None:
    result = await _call(weather, "get_weather_brief", {"city_id": "city_goi", "month": 1})
    assert result["season"] == "winter"
    assert result["is_recommended"] is True


async def test_poi_graph_server_traversal() -> None:
    pois = await _call(poi_graph, "pois_in_city", {"city_id": "city_goi"})
    assert len(pois) == 6
    cities = await _call(poi_graph, "cities_in_country", {"country_id": "ctry_in"})
    assert {c["id"] for c in cities} == {"city_bom", "city_goi"}


async def test_memory_server_profiles() -> None:
    personas = await _call(memory, "list_personas", {})
    assert len(personas) >= 3
    profile = await _call(memory, "get_traveler_profile", {"traveler_id": "tr_arjun"})
    assert profile["budget_tier"] == "premium"
