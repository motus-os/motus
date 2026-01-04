# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""
Motus Exception Classes.

Proper exception hierarchy for error handling throughout Motus.
"""

from typing import Optional


class MCError(Exception):
    """Base exception for all Motus errors."""

    def __init__(self, message: str, details: Optional[str] = None):
        self.message = message
        self.details = details
        super().__init__(message)

    def __str__(self) -> str:
        if self.details:
            return f"{self.message}: {self.details}"
        return self.message


class SessionError(MCError):
    """Error related to session operations."""

    def __init__(
        self, message: str, session_id: Optional[str] = None, details: Optional[str] = None
    ):
        self.session_id = session_id
        super().__init__(message, details)


class SessionNotFoundError(SessionError):
    """Session file or directory not found."""

    pass


class SessionParseError(SessionError):
    """Error parsing session transcript."""

    pass


class ConfigError(MCError):
    """Configuration-related error."""

    pass


class WebError(MCError):
    """Web UI related error."""

    pass


class WebSocketError(WebError):
    """WebSocket connection error."""

    pass


class ProcessDetectionError(MCError):
    """Error detecting running Claude processes."""

    pass


class TranscriptError(MCError):
    """Error reading or parsing transcript files."""

    pass


class DriftError(MCError):
    """Error in drift detection."""

    pass


class InvalidIntentError(DriftError):
    """Invalid user intent extraction."""

    pass


class InvalidSessionError(DriftError):
    """Invalid session ID or drift state."""

    pass


class ParseError(MCError):
    """
    Error parsing session content.

    Attributes:
        message: Human-readable error description.
        file_path: Path to file being parsed.
        line_number: Line where error occurred (if applicable).
        raw_content: Problematic content (truncated).
    """

    def __init__(
        self,
        message: str,
        file_path: Optional[str] = None,
        line_number: Optional[int] = None,
        raw_content: Optional[str] = None,
    ):
        self.file_path = file_path
        self.line_number = line_number
        self.raw_content = raw_content[:200] if raw_content else None
        super().__init__(message, self._format_details())

    def _format_details(self) -> str:
        """Format detailed error message."""
        parts = []
        if self.file_path:
            parts.append(f"file={self.file_path}")
        if self.line_number:
            parts.append(f"line={self.line_number}")
        if self.raw_content:
            parts.append(f"content={self.raw_content!r}")
        return " | ".join(parts) if parts else None


class TracerError(MCError):
    """Error in the Motus tracer/SDK."""

    pass


class HookError(MCError):
    """Error in Motus hooks."""

    pass


class SubprocessError(MCError):
    """Error running a subprocess."""

    def __init__(
        self, message: str, *, argv: list[str] | None = None, details: Optional[str] = None
    ):
        self.argv = list(argv or [])
        super().__init__(message, details)


class SubprocessTimeoutError(SubprocessError):
    """Subprocess exceeded its timeout."""

    def __init__(
        self,
        message: str,
        *,
        argv: list[str] | None = None,
        timeout_seconds: float | None = None,
        details: Optional[str] = None,
    ):
        self.timeout_seconds = timeout_seconds
        super().__init__(message, argv=argv, details=details)
