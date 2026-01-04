# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""
Session Orchestrator - Unified session management across all sources.

This is the single entry point for all session discovery, parsing, and management.
All surfaces (CLI, Web) should use this orchestrator instead of source-specific code.

PERFORMANCE: Lazy initialization - SessionOrchestrator only created when first accessed.
"""

# Re-export for backward compatibility
__all__ = [
    "SessionOrchestrator",
    "get_orchestrator",
    "MAX_CACHED_SESSIONS",
    "MAX_CACHED_EVENT_LISTS",
]


# Global orchestrator instance - created on first access
_orchestrator = None


def get_orchestrator():
    """
    Get the global SessionOrchestrator instance.

    This is the recommended way to access the orchestrator
    throughout the application.

    Lazy initialization ensures heavy imports only happen when needed.
    """
    global _orchestrator
    if _orchestrator is None:
        from .core import SessionOrchestrator

        _orchestrator = SessionOrchestrator()
    return _orchestrator


def __getattr__(name):
    """Lazy load orchestrator components."""
    if name == "SessionOrchestrator":
        from .core import SessionOrchestrator

        return SessionOrchestrator
    elif name == "MAX_CACHED_SESSIONS":
        from .cache import MAX_CACHED_SESSIONS

        return MAX_CACHED_SESSIONS
    elif name == "MAX_CACHED_EVENT_LISTS":
        from .cache import MAX_CACHED_EVENT_LISTS

        return MAX_CACHED_EVENT_LISTS
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
