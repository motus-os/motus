# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""MCP server implementation using FastMCP (stdio transport)."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from .tools import export_teleport, get_context, get_events, get_session, list_sessions


def create_server() -> FastMCP:
    """Create and configure the MCP server."""
    mcp = FastMCP("motus")

    mcp.tool(structured_output=True)(list_sessions)
    mcp.tool(structured_output=True)(get_session)
    mcp.tool(structured_output=True)(get_events)
    mcp.tool(structured_output=True)(get_context)
    mcp.tool(structured_output=True)(export_teleport)

    return mcp


def run_server() -> None:
    """Run the MCP server (stdio transport)."""
    server = create_server()
    server.run()
