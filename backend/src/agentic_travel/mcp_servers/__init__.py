"""MCP servers exposing the inventory/data services as tools.

Each module defines a standalone `FastMCP` server (`mcp`) so it can be run as
its own process and connected to from an ADK agent via an MCP toolset, keeping
the "MCP = tools and data" boundary explicit.
"""
