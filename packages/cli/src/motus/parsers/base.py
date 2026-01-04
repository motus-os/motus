# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Base parser interface for all agent-specific parsers.

This module defines the abstract base class that all parsers must inherit from.
It enforces a consistent interface for parsing raw event data from different
AI coding agents (Claude, Codex, Gemini, etc.).

Architecture:
- BaseParser is abstract - cannot be instantiated directly
- Subclasses MUST implement: parse(), can_parse()
- Subclasses MUST define: source (AgentSource)
- BaseParser provides: safe_parse() with error handling

Error Handling:
- parse() can raise exceptions - caught by safe_parse()
- safe_parse() logs errors and returns None on failure
- Parsers should return None for events they can't handle
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from motus.logging import get_logger
from motus.schema import AgentSource, ParsedEvent

logger = get_logger(__name__)


class BaseParser(ABC):
    """Abstract base class for event parsers.

    All agent-specific parsers must inherit from this class and implement
    the abstract methods. This ensures a consistent interface across all
    parsers and enables the parser registry to work correctly.

    Class Attributes:
        source: Which AI agent this parser handles (MUST be defined by subclass)

    Abstract Methods:
        can_parse: Check if this parser can handle the given raw data
        parse: Parse raw data into a ParsedEvent

    Concrete Methods:
        safe_parse: Wrapper around parse() with error handling

    Example:
        >>> class ClaudeParser(BaseParser):
        ...     source = AgentSource.CLAUDE
        ...
        ...     def can_parse(self, raw_data: dict) -> bool:
        ...         return raw_data.get("type") == "claude_event"
        ...
        ...     def parse(self, raw_data: dict) -> ParsedEvent | None:
        ...         return ParsedEvent(
        ...             session_id=raw_data["session_id"],
        ...             event_type=EventType.TOOL_USE,
        ...             source=self.source,
        ...         )
    """

    # Subclasses MUST override this with their specific AgentSource
    source: AgentSource

    @abstractmethod
    def can_parse(self, raw_data: dict[str, Any]) -> bool:
        """Check if this parser can handle the given raw data.

        This method should perform a quick check to determine if the raw_data
        structure matches what this parser expects. It should NOT do the full
        parsing - just validate the structure.

        Args:
            raw_data: Raw event data dictionary from the agent

        Returns:
            True if this parser can handle this data, False otherwise

        Example:
            >>> def can_parse(self, raw_data: dict) -> bool:
            ...     return raw_data.get("type") == "tool_use"
        """
        pass

    @abstractmethod
    def parse(self, raw_data: dict[str, Any]) -> ParsedEvent | None:
        """Parse raw event data into a ParsedEvent.

        This method performs the actual parsing logic. It should:
        1. Extract relevant fields from raw_data
        2. Map to the unified ParsedEvent schema
        3. Return None if the event should be skipped
        4. Raise exceptions for invalid/corrupt data

        Args:
            raw_data: Raw event data dictionary from the agent

        Returns:
            ParsedEvent if parsing succeeded, None if event should be skipped

        Raises:
            ValueError: If required fields are missing or invalid
            KeyError: If expected keys are not in raw_data
            Any other exception for parsing errors

        Example:
            >>> def parse(self, raw_data: dict) -> ParsedEvent | None:
            ...     if raw_data.get("skip"):
            ...         return None
            ...     return ParsedEvent(
            ...         session_id=raw_data["session_id"],
            ...         event_type=EventType.TOOL_USE,
            ...         source=self.source,
            ...         tool_name=raw_data["tool"],
            ...     )
        """
        pass

    def safe_parse(self, raw_data: dict[str, Any]) -> ParsedEvent | None:
        """Safely parse raw data with error handling.

        This is a concrete method that wraps parse() with try/except to handle
        any exceptions. It logs errors and returns None on failure, ensuring
        that one bad event doesn't crash the entire parsing process.

        The error handling flow:
        1. Call parse() on the raw_data
        2. If successful, return the ParsedEvent
        3. If parse() raises an exception, log it with context
        4. Return None to indicate parsing failed

        Args:
            raw_data: Raw event data dictionary from the agent

        Returns:
            ParsedEvent if parsing succeeded, None if parsing failed or was skipped

        Example:
            >>> parser = ClaudeParser()
            >>> event = parser.safe_parse({"type": "tool_use", "tool": "Read"})
            >>> if event:
            ...     print(f"Parsed: {event.event_type}")
        """
        try:
            return self.parse(raw_data)
        except (ValueError, KeyError, TypeError, AttributeError) as e:
            logger.error(
                "Failed to parse event",
                source=self.source.value,
                raw_data_type=type(raw_data).__name__,
                error_type=type(e).__name__,
                error=str(e),
                exc_info=True,
            )
            return None
