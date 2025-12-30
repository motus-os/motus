"""MCP server for Motus Command.

Exposes session data to MCP-compatible clients like Claude Desktop.
"""

from .server import create_server, run_server

__all__ = ["create_server", "run_server"]
