# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""
Event loading and parsing utilities.

This module provides utilities for loading events from sessions,
with support for caching, tail-based reading, and validation.
"""

from typing import List, Optional

from ..ingestors import BaseBuilder
from ..logging import get_logger
from ..policy.forensics_boundary import apply_forensics_boundary
from ..protocols import Source, UnifiedEvent, UnifiedSession
from ..schema.events import ParsedEvent
from .cache import SessionCache

logger = get_logger(__name__)

__all__ = [
    "load_events",
    "load_events_tail",
    "load_events_validated",
    "load_events_tail_validated",
]


def _apply_forensics_boundary(events: list[UnifiedEvent]) -> list[UnifiedEvent]:
    for event in events:
        event.raw_data = apply_forensics_boundary(getattr(event, "raw_data", None))
    return events


def load_events(
    session: UnifiedSession,
    builder: Optional[BaseBuilder],
    cache: SessionCache,
    refresh: bool = False,
) -> List[UnifiedEvent]:
    """
    Load all events for a session.

    Args:
        session: The session to get events for.
        builder: The builder for parsing events.
        cache: The cache instance.
        refresh: If True, bypass cache and re-parse.

    Returns:
        List of UnifiedEvent objects in chronological order.
    """
    cache_key = session.session_id

    if not refresh:
        cached = cache.get_events(cache_key)
        if cached is not None:
            return cached

    if not builder:
        return []

    try:
        events = _apply_forensics_boundary(builder.parse_events(session.file_path))
        cache.set_events(cache_key, events)
        cache.prune_caches()  # Prevent unbounded cache growth
        return events
    except Exception as e:
        logger.error(
            "Error parsing events",
            session_id=session.session_id,
            error_type=type(e).__name__,
            error=str(e),
        )
        return []


def load_events_tail(
    session: UnifiedSession,
    builder: Optional[BaseBuilder],
    n_lines: int = 200,
) -> List[UnifiedEvent]:
    """
    Load recent events using tail-based reading for large files.

    This is much faster than load_events() for large session files (~199MB)
    as it only reads the last N lines instead of parsing the entire file.
    Ideal for displays that only show recent events.

    Args:
        session: The session to get events for.
        builder: The builder for parsing events.
        n_lines: Number of lines to read from the end (default 200).

    Returns:
        List of UnifiedEvent objects in chronological order.
    """
    from ..tail_reader import tail_lines

    if not builder:
        return []

    # For non-JSONL sources (Gemini), fall back to full parse
    # Note: This requires access to the full parse method, so we need to handle this specially
    if session.source == Source.GEMINI:
        # For Gemini, we can't use tail reading efficiently
        # Caller should use load_events() and slice the result
        try:
            all_events = _apply_forensics_boundary(builder.parse_events(session.file_path))
            return all_events[-n_lines:] if len(all_events) > n_lines else all_events
        except Exception as e:
            logger.warning(
                "Error reading Gemini events",
                session_id=session.session_id,
                error_type=type(e).__name__,
                error=str(e),
            )
            return []

    try:
        # Read last N lines efficiently
        raw_lines = tail_lines(session.file_path, n_lines=n_lines)

        # Parse lines using builder's parse_line method
        tail_events: List[UnifiedEvent] = []
        session_id = session.session_id
        for line in raw_lines:
            try:
                parsed = builder.parse_line(line, session_id)
                tail_events.extend(parsed)
            except Exception as e:
                logger.warning(
                    "Failed to parse line in tail events",
                    session_id=session_id,
                    error_type=type(e).__name__,
                    error=str(e),
                )
                continue  # Skip unparseable lines

        return _apply_forensics_boundary(tail_events)
    except Exception as e:
        logger.warning(
            "Error reading tail events",
            session_id=session.session_id,
            error_type=type(e).__name__,
            error=str(e),
        )
        return []


def load_events_validated(
    session: UnifiedSession,
    builder: Optional[BaseBuilder],
    cache: SessionCache,
    refresh: bool = False,
) -> List[ParsedEvent]:
    """
    Load all events for a session as validated ParsedEvent instances.

    This is the preferred method for consumers that need schema-validated events.
    Events that fail Pydantic validation are logged and skipped.

    Args:
        session: The session to get events for.
        builder: The builder for parsing events.
        cache: The cache instance.
        refresh: If True, bypass cache and re-parse.

    Returns:
        List of validated ParsedEvent objects in chronological order.
    """
    cache_key = session.session_id

    if not refresh:
        cached = cache.get_parsed_events(cache_key)
        if cached is not None:
            return cached

    if not builder:
        return []

    try:
        events = builder.parse_events_validated(session.file_path)
        cache.set_parsed_events(cache_key, events)
        cache.prune_caches()
        return events
    except (OSError, ValueError, TypeError) as e:
        logger.error(
            "Error parsing validated events",
            session_id=session.session_id,
            error_type=type(e).__name__,
            error=str(e),
        )
        return []


def load_events_tail_validated(
    session: UnifiedSession,
    builder: Optional[BaseBuilder],
    n_lines: int = 200,
) -> List[ParsedEvent]:
    """
    Load recent events as validated ParsedEvent instances.

    This is the preferred method for CLI/Web displays that need
    validated events from large session files.

    Args:
        session: The session to get events for.
        builder: The builder for parsing events.
        n_lines: Number of lines to read from the end (default 200).

    Returns:
        List of validated ParsedEvent objects in chronological order.
    """
    from ..tail_reader import tail_lines

    if not builder:
        return []

    # For non-JSONL sources (Gemini), fall back to full parse
    if session.source == Source.GEMINI:
        try:
            all_events = builder.parse_events_validated(session.file_path)
            return all_events[-n_lines:] if len(all_events) > n_lines else all_events
        except (OSError, ValueError, TypeError) as e:
            logger.warning(
                "Error reading validated Gemini events",
                session_id=session.session_id,
                error_type=type(e).__name__,
                error=str(e),
            )
            return []

    try:
        raw_lines = tail_lines(session.file_path, n_lines=n_lines)

        # Parse lines using builder's validated parse_line method
        tail_events: List[ParsedEvent] = []
        session_id = session.session_id
        for line in raw_lines:
            try:
                parsed = builder.parse_line_validated(line, session_id)
                tail_events.extend(parsed)
            except (ValueError, TypeError) as e:
                logger.warning(
                    "Failed to parse line in validated tail events",
                    session_id=session_id,
                    error_type=type(e).__name__,
                    error=str(e),
                )
                continue  # Skip unparseable lines

        return tail_events
    except (OSError, ValueError, TypeError) as e:
        logger.warning(
            "Error reading validated tail events",
            session_id=session.session_id,
            error_type=type(e).__name__,
            error=str(e),
        )
        return []
