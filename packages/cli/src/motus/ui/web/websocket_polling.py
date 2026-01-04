# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Polling and event streaming helpers for WebSocketHandler."""

from __future__ import annotations

import asyncio
import json

from fastapi import WebSocket

from motus.config import config
from motus.logging import get_logger

logger = get_logger(__name__)


async def poll_events(self, websocket: WebSocket):
    """Poll for new events from Claude sessions."""
    # SYNC BOUNDARY: cached session refresh uses filesystem I/O via discover_all()
    io_timeout = config.web.io_timeout_seconds
    try:
        sessions = await asyncio.wait_for(
            asyncio.to_thread(self.session_state.get_cached_sessions),
            timeout=io_timeout,
        )
    except asyncio.TimeoutError:
        logger.warning("Web UI session discovery timed out")
        return

    current_session_ids = {s.session_id for s in sessions[:10]}

    # Periodically prune stale session data to prevent memory leaks
    self.session_state.prune_session_dicts(current_session_ids)
    known = self.ws_manager.get_known_sessions(websocket)
    new_sessions = current_session_ids - known

    if new_sessions:
        ws_module = self._websocket
        await websocket.send_json(
            {
                "type": "sessions",
                "sessions": [
                    {
                        "session_id": s.session_id,
                        "project_path": s.project_path,
                        "status": s.status.value,
                        "source": s.source.value,
                    }
                    for s in sessions[:10]
                ],
                "degraded": ws_module.get_orchestrator().is_process_degraded(),
                "errors": self.session_state.get_errors(),
            }
        )
        self.ws_manager.set_known_sessions(websocket, current_session_ids)

    active_sessions = [s for s in sessions if s.status.value in ("active", "open")]
    if not active_sessions:
        return

    session_event_batches = {}

    for session in active_sessions:
        session_id = session.session_id
        last_pos = self.session_state.get_position(session_id)

        # Initialize context if needed (ensures session_contexts dict has entry)
        self.session_state.get_context(session_id)

        try:
            # SYNC BOUNDARY: incremental parsing reads session files
            try:
                events, new_pos = await asyncio.wait_for(
                    asyncio.to_thread(
                        self._websocket.parse_incremental_events,
                        session=session,
                        last_pos=last_pos,
                        line_callback=None,
                        format_callback=None,
                    ),
                    timeout=io_timeout,
                )
            except asyncio.TimeoutError:
                logger.warning("Web UI session parse timed out", session_id=session_id)
                continue

            if new_pos != last_pos:
                self.session_state.set_position(session_id, new_pos)

            if events:
                session_event_batches[session_id] = {
                    "events": events,
                    "project_path": session.project_path,
                }

        except OSError as e:
            logger.debug(
                "Error reading session file",
                file_path=str(session.file_path),
                error_type=type(e).__name__,
                error=str(e),
            )
            self.session_state.set_error(session_id, f"File read error: {str(e)[:50]}")
        except Exception as e:
            logger.warning(
                "Unexpected error polling session",
                session_id=session_id,
                error_type=type(e).__name__,
                error=str(e),
            )
            self.session_state.set_error(session_id, f"Parsing error: {str(e)[:50]}")

    max_events = config.sessions.max_events_displayed
    all_events: list[dict] = []
    truncated = False
    for session_id, batch_data in session_event_batches.items():
        for event in batch_data["events"]:
            await update_context(self, websocket, event, session_id, batch_data["project_path"])
            formatted = self._websocket.format_event_for_client(
                event, session_id, batch_data["project_path"]
            )
            if formatted:
                if max_events > 0 and len(all_events) >= max_events:
                    truncated = True
                    break
                all_events.append(formatted)
        if truncated:
            break

    if all_events:
        await websocket.send_json(
            {"type": "batch_events", "count": len(all_events), "events": all_events}
        )


def check_for_user_intent(self, line: str, session_id: str, project_path: str):
    """Check if line contains a user message for UI hints (no enforcement)."""
    _ = (self, line, session_id, project_path)


async def update_context(self, websocket: WebSocket, event, session_id: str, project_path: str):
    """Update session context based on event (without sending to client).

    Tracks decisions, tool usage, files, and agents.
    """
    ctx = self.session_state.get_context(session_id)
    event_type = getattr(event, "event_type", None)
    if hasattr(event_type, "value"):
        event_type = event_type.value

    display_event = self._websocket.EventTransformer.transform(event)

    if event_type == self._websocket.EventType.THINKING.value:
        await track_thinking(self, event, ctx)
    elif event_type == self._websocket.EventType.AGENT_SPAWN.value:
        await track_agent_spawn(self, websocket, event, session_id, ctx, display_event)
    elif event_type == self._websocket.EventType.TOOL_USE.value:
        await track_tool_use(self, websocket, event, session_id, ctx, display_event)


async def track_thinking(self, event, ctx: dict):
    """Track thinking events for decisions and errors."""
    full_content = getattr(event, "content", "")
    decision_markers = ["i'll ", "i decided", "let me", "i should", "i'm going to"]
    content_lower = full_content.lower()

    for marker in decision_markers:
        if marker in content_lower:
            idx = content_lower.find(marker)
            end_idx = min(idx + 80, len(full_content))
            decision = full_content[idx:end_idx].replace("\n", " ").strip()
            if decision and decision not in ctx.get("decisions", []):
                if "decisions" not in ctx:
                    ctx["decisions"] = []
                safe_decision = self._websocket.SafeRenderer.content(decision, 60)
                ctx["decisions"].append(safe_decision)
                ctx["decisions"] = ctx["decisions"][-5:]
            break

    error_patterns = [
        "traceback (most recent call last)",
        "syntaxerror:",
        "typeerror:",
        "nameerror:",
        "command not found",
        "permission denied",
        "no such file or directory",
    ]
    if any(p in content_lower for p in error_patterns):
        ctx["friction_count"] = ctx.get("friction_count", 0) + 1


async def track_agent_spawn(self, websocket: WebSocket, event, session_id: str, ctx: dict, display_event):
    """Track agent spawn events."""
    spawn_type = getattr(event, "spawn_type", None) or getattr(event, "agent_type", "general")
    raw_data = getattr(event, "raw_data", None) or {}

    description, prompt, model = "", "", ""
    for detail in display_event.details:
        if detail.startswith("Model: "):
            model = detail[7:]
        elif detail.startswith("Prompt: "):
            prompt = detail[8:]
        else:
            description = detail

    context_text = (
        self._websocket.SafeRenderer.content(raw_data.get("context", ""), 100)
        if isinstance(raw_data, dict)
        else ""
    )

    ctx["agent_tree"].append(
        {
            "type": spawn_type,
            "desc": description[:50],
            "prompt": prompt[:100] if prompt else "",
            "full_prompt": prompt,
            "model": model,
            "context": context_text,
        }
    )
    ctx["agent_tree"] = ctx["agent_tree"][-5:]
    await websocket.send_json({"type": "context", "session_id": session_id, "context": ctx})


async def track_tool_use(self, websocket: WebSocket, event, session_id: str, ctx: dict, display_event):
    """Track tool use events."""
    tool_name = getattr(event, "tool_name", None) or "unknown"
    tool_input = getattr(event, "tool_input", {}) or {}
    if isinstance(tool_input, str):
        try:
            tool_input = json.loads(tool_input)
        except (json.JSONDecodeError, TypeError):
            tool_input = {}

    ctx["tool_count"][tool_name] = ctx["tool_count"].get(tool_name, 0) + 1

    if tool_name == "Read":
        path = tool_input.get("file_path", "")
        filename = path.split("/")[-1] if "/" in path else path
        if filename and filename not in ctx["files_read"]:
            ctx["files_read"].append(filename)
            ctx["files_read"] = ctx["files_read"][-10:]
    elif tool_name in ("Edit", "Write"):
        path = tool_input.get("file_path", "")
        filename = path.split("/")[-1] if "/" in path else path
        if filename and filename not in ctx["files_modified"]:
            ctx["files_modified"].append(filename)
            ctx["files_modified"] = ctx["files_modified"][-10:]
