# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""
LRU Cache Implementation for Session Management.

This module provides caching logic for sessions and events
with LRU (Least Recently Used) eviction policy.
"""

import time
from typing import Dict, List

from ..logging import get_logger
from ..protocols import UnifiedSession
from ..schema.events import ParsedEvent

# Cache size limits to prevent unbounded memory growth
MAX_CACHED_SESSIONS = 100
MAX_CACHED_EVENT_LISTS = 20

logger = get_logger(__name__)


class SessionCache:
    """Cache for session metadata with LRU eviction."""

    def __init__(self):
        """Initialize session cache."""
        self._session_cache: Dict[str, UnifiedSession] = {}
        self._event_cache: Dict[str, List] = {}
        self._event_access_times: Dict[str, float] = {}
        self._parsed_event_cache: Dict[str, List[ParsedEvent]] = {}
        self._parsed_event_access_times: Dict[str, float] = {}
        self._logger = get_logger(__name__)

    def prune_caches(self) -> None:
        """Prune caches to prevent unbounded memory growth."""
        # Prune session cache - only sort when significantly over limit (>120% instead of >100%)
        # This reduces unnecessary sorting on every cache operation
        threshold = int(MAX_CACHED_SESSIONS * 1.2)
        if len(self._session_cache) > threshold:
            sorted_sessions = sorted(
                self._session_cache.items(),
                key=lambda x: x[1].last_modified,
                reverse=True,
            )
            self._session_cache = dict(sorted_sessions[:MAX_CACHED_SESSIONS])
            self._logger.debug("Pruned session cache", entries=MAX_CACHED_SESSIONS)

        # Prune event cache - use LRU eviction based on access times
        while len(self._event_cache) > MAX_CACHED_EVENT_LISTS:
            # Remove least recently accessed entry (LRU)
            if self._event_access_times:
                lru_key = min(self._event_access_times, key=self._event_access_times.get)
                if lru_key in self._event_cache:
                    del self._event_cache[lru_key]
                if lru_key in self._event_access_times:
                    del self._event_access_times[lru_key]
                self._logger.debug("Pruned event cache (LRU)", evicted_key=lru_key)
            else:
                # Fallback: remove oldest inserted key if no access times tracked
                oldest_key = next(iter(self._event_cache))
                del self._event_cache[oldest_key]

        # Prune parsed event cache - use LRU eviction based on access times
        while len(self._parsed_event_cache) > MAX_CACHED_EVENT_LISTS:
            # Remove least recently accessed entry (LRU)
            if self._parsed_event_access_times:
                lru_key = min(
                    self._parsed_event_access_times, key=self._parsed_event_access_times.get
                )
                if lru_key in self._parsed_event_cache:
                    del self._parsed_event_cache[lru_key]
                if lru_key in self._parsed_event_access_times:
                    del self._parsed_event_access_times[lru_key]
                self._logger.debug("Pruned parsed event cache (LRU)", evicted_key=lru_key)
            else:
                # Fallback: remove oldest inserted key if no access times tracked
                oldest_key = next(iter(self._parsed_event_cache))
                del self._parsed_event_cache[oldest_key]

    def get_session(self, session_id: str) -> UnifiedSession | None:
        """Get a session from cache."""
        return self._session_cache.get(session_id)

    def set_session(self, session_id: str, session: UnifiedSession) -> None:
        """Add a session to cache."""
        self._session_cache[session_id] = session

    def get_events(self, session_id: str) -> List | None:
        """Get events from cache, updating access time."""
        if session_id in self._event_cache:
            self._event_access_times[session_id] = time.time()
            return self._event_cache[session_id]
        return None

    def set_events(self, session_id: str, events: List) -> None:
        """Add events to cache with access time."""
        self._event_cache[session_id] = events
        self._event_access_times[session_id] = time.time()

    def get_parsed_events(self, session_id: str) -> List[ParsedEvent] | None:
        """Get parsed events from cache, updating access time."""
        if session_id in self._parsed_event_cache:
            self._parsed_event_access_times[session_id] = time.time()
            return self._parsed_event_cache[session_id]
        return None

    def set_parsed_events(self, session_id: str, events: List[ParsedEvent]) -> None:
        """Add parsed events to cache with access time."""
        self._parsed_event_cache[session_id] = events
        self._parsed_event_access_times[session_id] = time.time()

    def clear_session(self, session_id: str) -> None:
        """Clear all cache entries for a session."""
        self._session_cache.pop(session_id, None)
        self._event_cache.pop(session_id, None)
        self._event_access_times.pop(session_id, None)
        self._parsed_event_cache.pop(session_id, None)
        self._parsed_event_access_times.pop(session_id, None)

    def clear_all(self) -> None:
        """Clear all caches."""
        self._session_cache.clear()
        self._event_cache.clear()
        self._event_access_times.clear()
        self._parsed_event_cache.clear()
        self._parsed_event_access_times.clear()
