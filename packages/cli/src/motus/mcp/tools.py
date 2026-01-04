# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""MCP tool implementations.

Each tool wraps orchestrator methods with MCP-compatible signatures.
Safety defaults: redact=True, tail_lines=200
"""

from __future__ import annotations

from typing import Any, TypedDict

from ..orchestrator import get_orchestrator
from ..protocols import Source, UnifiedSession
from .serialization import redact_obj, serialize_for_mcp


class ListSessionsResult(TypedDict):
    sessions: list[dict[str, Any]]


class GetSessionResult(TypedDict):
    session: dict[str, Any]


class GetEventsResult(TypedDict):
    events: list[dict[str, Any]]
    truncated: bool


class GetContextResult(TypedDict):
    context: dict[str, Any]


class ExportTeleportResult(TypedDict):
    bundle: dict[str, Any]


def _parse_sources(sources: list[str]) -> list[Source]:
    parsed: list[Source] = []
    for s in sources:
        try:
            parsed.append(Source(s))
        except ValueError:
            continue
    return parsed


def _resolve_session(session_id: str) -> UnifiedSession:
    orch = get_orchestrator()
    session = orch.get_session(session_id)
    if session is not None:
        return session

    # Prefix match (best-effort)
    candidates = [
        s for s in orch.discover_all(max_age_hours=168) if s.session_id.startswith(session_id)
    ]
    if not candidates:
        raise ValueError(f"Session not found: {session_id}")
    if len(candidates) > 1:
        raise ValueError(
            f"Ambiguous session prefix {session_id!r}: "
            + ", ".join(s.session_id for s in candidates[:10])
        )
    return candidates[0]


def list_sessions(
    max_age_hours: int = 24,
    sources: list[str] = ["claude", "codex", "gemini", "sdk"],
    limit: int = 50,
) -> ListSessionsResult:
    """List recent AI agent sessions observed by Motus."""
    limit = max(1, min(int(limit), 200))
    max_age_hours = max(1, int(max_age_hours))

    orch = get_orchestrator()
    source_enums = _parse_sources(sources)
    # Orchestrator currently supports only its configured ingestors; unknown sources are ignored.
    sessions = orch.discover_all(max_age_hours=max_age_hours, sources=source_enums or None)[:limit]
    serialized = [serialize_for_mcp(s) for s in sessions]
    # Always redact list outputs (project paths can leak user home paths).
    return {"sessions": redact_obj(serialized)}


def get_session(session_id: str, redact: bool = True) -> GetSessionResult:
    """Fetch a single session by ID (prefix match supported)."""
    session = _resolve_session(session_id)
    payload = serialize_for_mcp(session)
    return {"session": redact_obj(payload) if redact else payload}


def get_events(
    session_id: str,
    validated: bool = False,
    tail_lines: int = 200,
    full: bool = False,
    redact: bool = True,
    include_raw_data: bool = False,
) -> GetEventsResult:
    """Return events for a session (tail by default)."""
    session = _resolve_session(session_id)
    orch = get_orchestrator()

    tail_lines = max(10, min(int(tail_lines), 5000))

    truncated = not full
    if full:
        events = orch.get_events_validated(session) if validated else orch.get_events(session)
    else:
        events = (
            orch.get_events_tail_validated(session, n_lines=tail_lines)
            if validated
            else orch.get_events_tail(session, n_lines=tail_lines)
        )

    serialized_events: list[dict[str, Any]] = []
    for ev in events:
        d = serialize_for_mcp(ev)
        if isinstance(d, dict) and not include_raw_data:
            d.pop("raw_data", None)
        serialized_events.append(d)

    if redact:
        serialized_events = redact_obj(serialized_events)

    return {"events": serialized_events, "truncated": truncated}


def get_context(session_id: str, redact: bool = True) -> GetContextResult:
    """Return aggregated session context."""
    session = _resolve_session(session_id)
    orch = get_orchestrator()
    context = serialize_for_mcp(orch.get_context(session))
    return {"context": redact_obj(context) if redact else context}


def export_teleport(
    session_id: str, include_planning_docs: bool = True, redact: bool = True
) -> ExportTeleportResult:
    """Export a safe teleport bundle for cross-session handoffs."""
    session = _resolve_session(session_id)
    orch = get_orchestrator()
    bundle = orch.export_teleport(session, include_planning_docs=include_planning_docs)
    payload = serialize_for_mcp(bundle)
    # Ensure the session id can't leak as a full path if it was embedded anywhere.
    if redact and isinstance(payload, dict):
        payload = redact_obj(payload)
    return {"bundle": payload}
