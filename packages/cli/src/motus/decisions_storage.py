# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Decision extraction that depends on session storage."""

from __future__ import annotations

import importlib
from datetime import datetime
from pathlib import Path
from typing import Optional

from .decisions_core import Decision, DecisionLedger, extract_decision_from_text
from .logging import get_logger
from .schema.events import EventType

logger = get_logger(__name__)


def _get_decisions_module():
    module_name = f"{__package__}.decisions" if __package__ else "motus.decisions"
    return importlib.import_module(module_name)


def extract_decisions_from_session(
    session_path: Path,
    source: str = "claude",
) -> list[Decision]:
    """Extract decisions from a session transcript."""
    decisions: list[Decision] = []
    _ = source
    decisions_module = _get_decisions_module()
    orch = decisions_module.get_orchestrator()

    try:
        sessions = orch.discover_all(max_age_hours=168)
        target_session = None

        for session in sessions:
            if session.file_path == session_path:
                target_session = session
                break

        if not target_session:
            logger.debug(
                "Session not found for path",
                session_path=str(session_path),
            )
            return decisions

        events = orch.get_events_validated(target_session)

        for event in events:
            if event.event_type == EventType.THINKING:
                content = event.content or ""
                if len(content) > 50:
                    decision = extract_decision_from_text(content)
                    if decision:
                        decisions.append(decision)

    except Exception as e:
        logger.debug(
            "Error extracting decisions",
            session_path=str(session_path),
            error_type=type(e).__name__,
            error=str(e),
        )

    return decisions


def get_decisions(
    session_id: Optional[str] = None,
    session_path: Optional[Path] = None,
) -> DecisionLedger:
    """Get decisions from a session."""
    if session_path:
        decisions = extract_decisions_from_session(session_path)
        return DecisionLedger(
            session_id=session_path.stem,
            decisions=decisions,
            timestamp=datetime.now().isoformat(),
        )

    decisions_module = _get_decisions_module()
    orch = decisions_module.get_orchestrator()
    sessions = orch.discover_all(max_age_hours=24)

    if not sessions:
        return DecisionLedger(
            session_id="none",
            decisions=[],
            timestamp=datetime.now().isoformat(),
        )

    target_session = None
    if session_id:
        for session in sessions:
            if session.session_id.startswith(session_id):
                target_session = session
                break
    else:
        target_session = sessions[0]

    if not target_session:
        return DecisionLedger(
            session_id=session_id or "unknown",
            decisions=[],
            timestamp=datetime.now().isoformat(),
        )

    decisions = extract_decisions_from_session(
        target_session.file_path,
        target_session.source,
    )

    return DecisionLedger(
        session_id=target_session.session_id,
        decisions=decisions,
        timestamp=datetime.now().isoformat(),
    )
