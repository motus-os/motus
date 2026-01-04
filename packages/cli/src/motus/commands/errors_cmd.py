# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Extract and summarize errors from session files (`motus errors`)."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from rich.console import Console

from motus.cli.exit_codes import EXIT_ERROR, EXIT_SUCCESS, EXIT_USAGE
from motus.logging import get_logger

from ..errors.extractor import ErrorCategory, ErrorSummary, extract_errors_from_jsonl
from ..errors.formatter import print_error_summary, summary_to_json
from ..orchestrator import get_orchestrator

logger = get_logger(__name__)
console = Console()


def _resolve_session_by_id(session_id: str):
    orchestrator = get_orchestrator()
    sessions = orchestrator.discover_all(max_age_hours=168)
    for session in sessions:
        if session.session_id == session_id or session.session_id.startswith(session_id):
            return session
    return None


def _summarize_path(session_path: Path, *, category: Optional[ErrorCategory]) -> ErrorSummary:
    return extract_errors_from_jsonl(session_path, category=category)


def errors_command(args) -> int:
    session_path: Optional[Path] = None

    if getattr(args, "session", None):
        session_path = Path(args.session).expanduser()
    else:
        last = getattr(args, "last", None)
        if last is not None:
            orchestrator = get_orchestrator()
            sessions = orchestrator.discover_all(max_age_hours=168)

            try:
                n = max(1, min(int(last), 50))
            except (TypeError, ValueError):
                raise SystemExit(EXIT_USAGE)

            selected = sessions[:n]
            if not selected:
                raise SystemExit(EXIT_ERROR)

            category: Optional[ErrorCategory] = None
            if getattr(args, "category", None):
                try:
                    category = ErrorCategory(str(args.category).lower())
                except ValueError:
                    raise SystemExit(EXIT_USAGE)

            summaries = [_summarize_path(s.file_path, category=category) for s in selected]

            if getattr(args, "json", False):
                import json

                console.print(
                    json.dumps(
                        {
                            "sessions": [s.session_id for s in selected],
                            "summaries": [s.to_dict() for s in summaries],
                        },
                        indent=2,
                        sort_keys=True,
                    ),
                    markup=False,
                )
                return EXIT_SUCCESS

            for session, summary in zip(selected, summaries, strict=True):
                console.print()
                console.print(f"Session: {session.session_id}", markup=False)
                print_error_summary(summary)
            return EXIT_SUCCESS

        session_id = getattr(args, "session_id", None)
        if session_id:
            session = _resolve_session_by_id(session_id)
        else:
            orchestrator = get_orchestrator()
            sessions = orchestrator.discover_all(max_age_hours=24)
            session = sessions[0] if sessions else None

        if session is None:
            raise SystemExit(EXIT_ERROR)
        session_path = session.file_path

    if session_path is None or not session_path.exists():
        raise SystemExit(EXIT_ERROR)

    category: Optional[ErrorCategory] = None
    if getattr(args, "category", None):
        try:
            category = ErrorCategory(str(args.category).lower())
        except ValueError:
            raise SystemExit(EXIT_USAGE)

    summary = _summarize_path(session_path, category=category)

    if getattr(args, "json", False):
        console.print(summary_to_json(summary), markup=False)
        return EXIT_SUCCESS

    print_error_summary(summary)
    return EXIT_SUCCESS
