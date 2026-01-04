# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Module entrypoint for `python -m motus.mcp`."""

from .server import run_server


def main() -> None:
    """Run the MCP server entrypoint."""
    run_server()


if __name__ == "__main__":
    main()
