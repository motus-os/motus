# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""MCP server for Motus.

Exposes session data to MCP-compatible clients like Claude Desktop.
"""

from .server import create_server, run_server

__all__ = ["create_server", "run_server"]
