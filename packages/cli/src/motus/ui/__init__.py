"""UI package for Motus Command.

The Textual-based TUI was removed in v0.5.0. The Web UI is the primary interface.
"""

__all__ = ["run_web", "MCWebServer"]


def __getattr__(name):
    if name in ("run_web", "MCWebServer"):
        from .web import MCWebServer, run_web

        return {"run_web": run_web, "MCWebServer": MCWebServer}[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
