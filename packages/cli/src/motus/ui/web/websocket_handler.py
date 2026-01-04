# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""WebSocket handler for the Motus Web UI."""

import asyncio
import importlib
import time

from fastapi import WebSocket, WebSocketDisconnect

from motus.config import config
from motus.logging import get_logger
from motus.ui.web import websocket_polling
from motus.ui.web.state import SessionState
from motus.ui.web.websocket_manager import WebSocketManager

logger = get_logger(__name__)


class WebSocketHandler:
    """Handles WebSocket connections and messaging for the web UI."""

    _poll_events = websocket_polling.poll_events
    _check_for_user_intent = websocket_polling.check_for_user_intent
    _update_context = websocket_polling.update_context
    _track_thinking = websocket_polling.track_thinking
    _track_agent_spawn = websocket_polling.track_agent_spawn
    _track_tool_use = websocket_polling.track_tool_use

    def __init__(self, ws_manager: WebSocketManager, session_state: SessionState):
        """Initialize WebSocket handler."""
        self.ws_manager = ws_manager
        self.session_state = session_state
        self.drift_detector = None
        self._websocket = importlib.import_module("motus.ui.web.websocket")

    async def _run_blocking(
        self,
        func,
        *args,
        timeout: float,
        default,
        context: str,
        **kwargs,
    ):
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(func, *args, **kwargs),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            logger.warning("Web UI blocking call timed out", operation=context)
            return default

    async def handle_connection(self, websocket: WebSocket):
        """Handle a WebSocket connection lifecycle."""
        # Defense-in-depth: validate origin (server already binds to localhost only)
        origin = websocket.headers.get("origin", "")
        if origin and not any(
            origin.startswith(allowed)
            for allowed in ("http://localhost", "http://127.0.0.1")
        ):
            logger.warning("WebSocket connection rejected: invalid origin", origin=origin)
            await websocket.close(code=1008, reason="Invalid origin")
            return

        await websocket.accept()
        # First response should be fast; the client ignores unknown message types.
        await websocket.send_json({"type": "connected"})
        self.ws_manager.add_client(websocket)
        try:
            # Send initial sessions and track known sessions
            orchestrator = self._websocket.get_orchestrator()
            # SYNC BOUNDARY: session discovery performs filesystem I/O
            io_timeout = config.web.io_timeout_seconds
            sessions = await self._run_blocking(
                orchestrator.discover_all,
                max_age_hours=24,
                timeout=io_timeout,
                default=[],
                context="discover_all",
            )
            self.ws_manager.set_known_sessions(websocket, {s.session_id for s in sessions[:10]})

            # Build session data with last_action for crashed sessions
            session_data = []
            for s in sessions[:10]:
                data = {
                    "session_id": s.session_id,
                    "project_path": s.project_path,
                    "status": s.status.value,  # Convert enum to string
                    "source": s.source.value,  # Convert enum to string
                }
                # Add last_action for crashed sessions
                if s.status.value == "crashed":
                    builder = orchestrator.get_builder(s.source)
                    if builder:
                        # SYNC BOUNDARY: last_action may read the filesystem
                        data["last_action"] = await self._run_blocking(
                            builder.get_last_action,
                            s.file_path,
                            timeout=io_timeout,
                            default=None,
                            context="get_last_action",
                        )
                session_data.append(data)

            await websocket.send_json(
                {
                    "type": "sessions",
                    "sessions": session_data,
                }
            )

            timeout_seconds = config.web.session_timeout_seconds
            deadline = None
            if timeout_seconds > 0:
                deadline = time.monotonic() + timeout_seconds

            # Handle messages
            while True:
                if deadline is not None and time.monotonic() >= deadline:
                    logger.info("WebSocket session timed out")
                    await websocket.close(code=1001, reason="Session timeout")
                    break
                try:
                    data = await asyncio.wait_for(websocket.receive_json(), timeout=1.0)
                    await self._handle_client_message(websocket, data)
                except asyncio.TimeoutError:
                    # Poll for new events
                    await self._poll_events(websocket)
                except WebSocketDisconnect:
                    break
        finally:
            self.ws_manager.remove_client(websocket)

    async def _handle_client_message(self, websocket: WebSocket, data: dict):
        """Handle incoming client messages."""
        msg_type = data.get("type")
        if msg_type == "select_session":
            session_id = data.get("session_id")
            # Send context if available
            if session_id and session_id in self.session_state.session_contexts:
                await websocket.send_json(
                    {
                        "type": "context",
                        "session_id": session_id,
                        "context": self.session_state.session_contexts[session_id],
                    }
                )
            # Load FULL history and intents for selected session
            if session_id:
                await self._send_session_history(websocket, session_id)
                await self._send_session_intents(websocket, session_id)
        elif msg_type == "request_backfill":
            # Load recent historical events for all active sessions
            await self._send_backfill(websocket, data.get("limit", 30))
        elif msg_type == "request_intents":
            # Get user intents for a session using enhanced parser
            session_id = data.get("session_id")
            if session_id:
                await self._send_session_intents(websocket, session_id)
        elif msg_type == "load_more":
            # Load more historical events for pagination
            session_id = data.get("session_id")
            offset = data.get("offset", 0)
            if session_id:
                await self._send_session_history(websocket, session_id, offset=offset)
        elif msg_type == "heartbeat":
            pass  # Keep-alive

    async def _send_session_history(self, websocket: WebSocket, session_id: str, offset: int = 0):
        """Send history for a specific session with fast tail-based loading."""
        # SYNC BOUNDARY: history parsing reads the session file
        io_timeout = config.web.io_timeout_seconds
        result = await self._run_blocking(
            self._websocket.parse_session_history,
            session_id=session_id,
            offset=offset,
            batch_size=200,
            format_callback=self._websocket.format_event_for_client,
            timeout=io_timeout,
            default={
                "error": "Session history timed out",
                "events": [],
                "total_events": 0,
                "has_more": False,
                "offset": offset,
            },
            context="parse_session_history",
        )

        if result["error"]:
            await websocket.send_json(
                {"type": "error", "session_id": session_id, "message": result["error"]}
            )
            return

        await websocket.send_json(
            {
                "type": "session_history",
                "session_id": session_id,
                "events": result["events"],
                "total_events": result["total_events"],
                "has_more": result["has_more"],
                "offset": result["offset"],
            }
        )

    async def _send_backfill(self, websocket: WebSocket, limit: int = 30):
        """Send historical events to client on connect/refresh."""
        orchestrator = self._websocket.get_orchestrator()
        # SYNC BOUNDARY: session discovery performs filesystem I/O
        io_timeout = config.web.io_timeout_seconds
        sessions = await self._run_blocking(
            orchestrator.discover_all,
            max_age_hours=24,
            timeout=io_timeout,
            default=[],
            context="backfill_discover_all",
        )

        # SYNC BOUNDARY: backfill parsing reads session files
        backfill_events = await self._run_blocking(
            self._websocket.parse_backfill_events,
            sessions=sessions,
            limit=limit,
            format_callback=self._websocket.format_event_for_client,
            timeout=io_timeout,
            default=[],
            context="parse_backfill_events",
        )

        await websocket.send_json({"type": "backfill", "events": backfill_events})

    async def _send_session_intents(self, websocket: WebSocket, session_id: str):
        """Extract and send user intents for a session."""
        # SYNC BOUNDARY: intent parsing reads session files
        io_timeout = config.web.io_timeout_seconds
        result = await self._run_blocking(
            self._websocket.parse_session_intents,
            session_id,
            timeout=io_timeout,
            default={"error": "Session intents timed out"},
            context="parse_session_intents",
        )

        if result.get("error"):
            logger.warning(
                "Error extracting intents for session",
                session_id=session_id,
                error=result["error"],
            )
            return

        await websocket.send_json(
            {
                "type": "session_intents",
                "session_id": session_id,
                "intents": result["intents"],
                "stats": result["stats"],
            }
        )
