# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""
State management for Motus Web UI.

Manages session state, caching, and context tracking.
"""

import time

from motus.logging import get_logger
from motus.orchestrator import get_orchestrator

logger = get_logger(__name__)


class SessionState:
    """Manages session state and caching for the web UI.

    Tracks:
    - Session positions for incremental reading
    - Session contexts (decisions, tool usage, files)
    - Agent spawn stacks
    - Parsing errors
    - Cached session list with TTL
    """

    # Maximum number of sessions to track in memory to prevent unbounded growth
    MAX_TRACKED_SESSIONS = 50

    def __init__(self):
        """Initialize session state."""
        self.session_positions: dict[str, int] = {}
        self.session_contexts: dict[str, dict] = {}
        self.agent_stacks: dict[str, list[str]] = {}
        self.parsing_errors: dict[str, str] = {}

        # Cached session list - refreshed every 5 seconds instead of every poll
        self._cached_sessions: list = []
        self._sessions_cache_time: float = 0
        self._sessions_cache_ttl: float = 5.0  # Refresh every 5 seconds

    def get_cached_sessions(self):
        """Get sessions from cache, refreshing if TTL expired.

        Returns cached sessions if within TTL (5 seconds), otherwise
        refreshes the cache. This reduces discover_all() calls from
        once per poll (every 1s) to once per TTL (every 5s).
        """
        now = time.time()
        if now - self._sessions_cache_time > self._sessions_cache_ttl:
            self._cached_sessions = get_orchestrator().discover_all(max_age_hours=24)
            self._sessions_cache_time = now
        return self._cached_sessions

    def prune_session_dicts(self, active_session_ids: set[str]) -> None:
        """Remove stale session data from internal dicts to prevent memory leaks.

        Called periodically during polling. Keeps only sessions that are currently
        active, plus recent sessions up to MAX_TRACKED_SESSIONS.
        """
        # Get all tracked session IDs
        all_tracked = set(self.session_positions.keys())

        # If under limit, no pruning needed
        if len(all_tracked) <= self.MAX_TRACKED_SESSIONS:
            return

        # Keep active sessions, prune the rest
        to_remove = all_tracked - active_session_ids

        # Remove from all dicts
        for session_id in to_remove:
            self.session_positions.pop(session_id, None)
            self.session_contexts.pop(session_id, None)
            self.agent_stacks.pop(session_id, None)
            self.parsing_errors.pop(session_id, None)

    def prune_stale_sessions(self, active_session_ids: set[str]) -> None:
        """Alias for backward compatibility with tests."""
        self.prune_session_dicts(active_session_ids)

    def get_context(self, session_id: str) -> dict:
        """Get or initialize context for a session."""
        if session_id not in self.session_contexts:
            self.session_contexts[session_id] = {
                "files_read": [],
                "files_modified": [],
                "agent_tree": [],
                "decisions": [],
                "tool_count": {},
            }
        return self.session_contexts[session_id]

    def get_position(self, session_id: str) -> int:
        """Get last read position for a session."""
        return self.session_positions.get(session_id, 0)

    def set_position(self, session_id: str, position: int) -> None:
        """Set last read position for a session."""
        self.session_positions[session_id] = position

    def set_error(self, session_id: str, error: str) -> None:
        """Record a parsing error for a session."""
        self.parsing_errors[session_id] = error

    def get_errors(self) -> dict[str, str]:
        """Get all parsing errors."""
        return self.parsing_errors

    def has_context(self, session_id: str) -> bool:
        """Check if context exists for a session."""
        return session_id in self.session_contexts

    def get_agent_stack(self, session_id: str) -> list[str]:
        """Get agent stack for a session."""
        return self.agent_stacks.get(session_id, [])

    def set_agent_stack(self, session_id: str, stack: list[str]) -> None:
        """Set agent stack for a session."""
        self.agent_stacks[session_id] = stack

    def get_parsing_error(self, session_id: str) -> str | None:
        """Get parsing error for a session."""
        return self.parsing_errors.get(session_id)

    def set_parsing_error(self, session_id: str, error: str) -> None:
        """Record a parsing error for a session."""
        self.parsing_errors[session_id] = error

    def get_all_parsing_errors(self) -> dict[str, str]:
        """Get all parsing errors."""
        return self.parsing_errors.copy()
