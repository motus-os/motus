# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""
Motus: Command Center for AI Agents

Real-time observability and memory for AI coding assistants.

Usage:
    # CLI
    $ motus watch  # Watch active Claude session
    $ motus list   # List sessions
    $ motus summary  # Generate AI memory for CLAUDE.md

    # SDK (for any Python agent)
    from motus import Tracer

    tracer = Tracer("my-agent")

    @tracer.track
    def my_agent_step(prompt):
        # Your agent logic
        return response

    # Or explicit logging
    tracer.thinking("Deciding which approach...")
    tracer.tool("WebSearch", {"query": "python tips"})
    tracer.decision("Using async because batch is large")
"""

try:
    from importlib.metadata import PackageNotFoundError, version

    # Try published package name first, then editable install name
    try:
        __version__ = version("motusos")
    except PackageNotFoundError:
        __version__ = version("motus")
except PackageNotFoundError:
    # Fallback for editable installs when package metadata unavailable
    __version__ = "0.1.1"

__author__ = "Motus Contributors"

# PERFORMANCE: Lazy imports to reduce CLI startup time
# Only import lightweight modules at package level
# Heavy dependencies (Pydantic, Rich, FastAPI) loaded on-demand

# Lightweight imports - safe for package init
# Exceptions - lightweight, no heavy dependencies
from .exceptions import (
    ConfigError,
    MCError,
    SessionError,
    SessionNotFoundError,
    SessionParseError,
    TranscriptError,
    WebError,
)
from .logging import get_logger


# Lazy loading helpers for heavy imports
def _get_config():
    """Lazy load config module."""
    from .config import config

    return config


def _get_mc_config():
    """Lazy load MCConfig class."""
    from .config import MCConfig

    return MCConfig


def _get_tracer():
    """Lazy load Tracer class."""
    from .tracer import Tracer

    return Tracer


def _get_tracer_instance():
    """Lazy load get_tracer function."""
    from .tracer import get_tracer

    return get_tracer


# Cache for lazy-loaded modules to avoid recursion
_lazy_cache: dict[str, object] = {}


# Re-export with lazy loading via __getattr__
def __getattr__(name):
    """Lazy load heavy modules on attribute access."""
    # Check cache first to avoid recursion
    if name in _lazy_cache:
        return _lazy_cache[name]

    # Config
    if name == "config":
        result = _get_config()
    elif name == "MCConfig":
        result = _get_mc_config()
    # Tracer SDK
    elif name == "Tracer":
        result = _get_tracer()
    elif name == "get_tracer":
        result = _get_tracer_instance()
    # Messages module
    elif name == "messages":
        import importlib

        result = importlib.import_module(".messages", __name__)
    # Events - heavy due to Pydantic
    elif name in ("ThinkingEvent", "ToolEvent", "DecisionEvent"):
        from .events import DecisionEvent, ThinkingEvent, ToolEvent

        result = {
            "ThinkingEvent": ThinkingEvent,
            "ToolEvent": ToolEvent,
            "DecisionEvent": DecisionEvent,
        }[name]
    else:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    # Cache the result
    _lazy_cache[name] = result
    return result


__all__ = [
    # SDK
    "Tracer",
    "get_tracer",
    # Events
    "ThinkingEvent",
    "ToolEvent",
    "DecisionEvent",
    # Config
    "config",
    "MCConfig",
    # Logging
    "get_logger",
    # Messages
    "messages",
    # Exceptions
    "MCError",
    "SessionError",
    "SessionNotFoundError",
    "SessionParseError",
    "ConfigError",
    "WebError",
    "TranscriptError",
    # Meta
    "__version__",
]
