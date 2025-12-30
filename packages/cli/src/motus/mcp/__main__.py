"""Module entrypoint for `python -m motus.mcp`."""

from .server import run_server


def main() -> None:
    """Run the MCP server entrypoint."""
    run_server()


if __name__ == "__main__":
    main()
