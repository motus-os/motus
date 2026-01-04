# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Standardized user-facing messages for consistent UX across surfaces."""

# Empty States
NO_SESSIONS = (
    "No active sessions found. Start a Claude, Codex, or Gemini session to begin monitoring."
)
NO_SESSIONS_SHORT = "No active sessions"
NO_EVENTS = "No events in this session. The session may be idle or just started."
NO_EVENTS_SHORT = "No events yet"

# Error States
SESSION_NOT_FOUND = "Session '{session_id}' not found. Run 'motus list' to see available sessions."
SESSION_NOT_FOUND_SHORT = "Session not found"
PARSE_ERROR = "Failed to parse session data. The session file may be corrupted."
CONNECTION_ERROR = "Failed to connect. Check that the service is running."

# Status Messages
LOADING = "Loading..."
REFRESHING = "Refreshing..."
WATCHING = "Watching session '{session_id}'..."


# Helper Functions
def session_not_found(session_id: str) -> str:
    """Format session not found message with ID."""
    return SESSION_NOT_FOUND.format(session_id=session_id)


def watching(session_id: str) -> str:
    """Format watching message with ID."""
    return WATCHING.format(session_id=session_id)


# For Web API (JSON-friendly)
def error_response(code: str, message: str, **kwargs) -> dict:
    """Create standardized error response for Web API."""
    return {"error": code, "message": message, **kwargs}
