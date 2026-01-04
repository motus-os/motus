# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""
WebSocket client management for Motus Web UI.

Handles client tracking and session awareness.
Extracted from server.py to separate concerns.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

WEB_AVAILABLE: bool

if TYPE_CHECKING:
    from fastapi import WebSocket

    WEB_AVAILABLE = True
else:
    try:
        from fastapi import WebSocket

        WEB_AVAILABLE = True
    except ImportError:  # pragma: no cover
        WEB_AVAILABLE = False

        class WebSocket:  # type: ignore[no-redef]
            pass


class WebSocketManager:
    """Manages WebSocket client connections and per-client state."""

    def __init__(self):
        """Initialize the WebSocket manager."""
        self.clients: set[WebSocket] = set()
        self.known_sessions: dict[WebSocket, set] = {}

    def add_client(self, websocket: WebSocket) -> None:
        """Register a new WebSocket client.

        Args:
            websocket: The WebSocket connection to register
        """
        self.clients.add(websocket)
        self.known_sessions[websocket] = set()

    def remove_client(self, websocket: WebSocket) -> None:
        """Unregister a WebSocket client and cleanup its state.

        Args:
            websocket: The WebSocket connection to unregister
        """
        self.clients.discard(websocket)
        self.known_sessions.pop(websocket, None)

    def get_known_sessions(self, websocket: WebSocket) -> set:
        """Get the set of session IDs known to a specific client.

        Args:
            websocket: The WebSocket connection to query

        Returns:
            Set of session IDs the client knows about
        """
        return self.known_sessions.get(websocket, set())

    def set_known_sessions(self, websocket: WebSocket, session_ids: set) -> None:
        """Update the set of session IDs known to a specific client.

        Args:
            websocket: The WebSocket connection to update
            session_ids: Set of session IDs to mark as known
        """
        self.known_sessions[websocket] = session_ids

    def get_client_count(self) -> int:
        """Get the number of connected clients.

        Returns:
            Number of active WebSocket connections
        """
        return len(self.clients)
