# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Activity proof ledger (append-only JSONL).

This ledger captures high-level activity events (CLI invocations, IO, network)
as immutable JSONL lines under `.motus/state/ledger/`. It is best-effort:
logging failures never block core execution.
"""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator

from motus.core.bootstrap import get_instance_id

ACTIVITY_SCHEMA = "motus.activity.v1"
DEFAULT_ACTIVITY_FILENAME = "activity.jsonl"
MAX_FIELD_CHARS = int(os.environ.get("MOTUS_ACTIVITY_MAX_FIELD_CHARS", "2048"))


def _utc_now_iso_z() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _should_log() -> bool:
    raw = os.environ.get("MOTUS_ACTIVITY_ENABLED", "1").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def _ledger_dir() -> Path | None:
    if not _should_log():
        return None

    override = os.environ.get("MOTUS_ACTIVITY_DIR", "").strip()
    if override:
        return Path(override).expanduser()

    motus_dir = _find_motus_dir(Path.cwd())
    if motus_dir is None:
        return Path.home() / ".motus" / "state" / "ledger"
    return motus_dir / "state" / "ledger"


def _truncate(value: str | None) -> str | None:
    if value is None:
        return None
    if len(value) <= MAX_FIELD_CHARS:
        return value
    return value[: MAX_FIELD_CHARS - 3] + "..."


def _sanitize_dict(data: dict[str, Any] | None) -> dict[str, Any] | None:
    if data is None:
        return None
    sanitized: dict[str, Any] = {}
    for key, value in data.items():
        if isinstance(value, str):
            sanitized[key] = _truncate(value)
        else:
            sanitized[key] = value
    return sanitized


def _event_id() -> str:
    return f"act-{uuid.uuid4().hex}"


def _safe_instance_id() -> str:
    try:
        return get_instance_id()
    except Exception:
        return "unknown"


def _find_motus_dir(start: Path) -> Path | None:
    for base in [start, *start.parents]:
        motus_dir = base / ".motus"
        if motus_dir.exists() and motus_dir.is_dir():
            return motus_dir
    return None


@dataclass(frozen=True, slots=True)
class ActivityEvent:
    event_id: str
    timestamp: str
    actor: str
    category: str
    action: str
    subject: dict[str, Any]
    context: dict[str, Any] | None = None
    instance_id: str | None = None
    schema: str = ACTIVITY_SCHEMA

    def to_json(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schema": self.schema,
            "event_id": self.event_id,
            "timestamp": self.timestamp,
            "actor": self.actor,
            "category": self.category,
            "action": self.action,
            "subject": _sanitize_dict(self.subject) or {},
        }
        if self.context is not None:
            payload["context"] = _sanitize_dict(self.context) or {}
        if self.instance_id is not None:
            payload["instance_id"] = self.instance_id
        return payload


class ActivityLedger:
    """Append-only ledger for activity events."""

    def __init__(self, ledger_dir: Path | None = None) -> None:
        self._dir = ledger_dir or _ledger_dir()

    def emit(
        self,
        *,
        actor: str,
        category: str,
        action: str,
        subject: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> Path | None:
        if self._dir is None:
            return None

        self._dir.mkdir(parents=True, exist_ok=True)
        path = self._dir / DEFAULT_ACTIVITY_FILENAME

        event = ActivityEvent(
            event_id=_event_id(),
            timestamp=_utc_now_iso_z(),
            actor=actor,
            category=category,
            action=action,
            subject=subject,
            context=context,
            instance_id=_safe_instance_id(),
        )
        line = json.dumps(event.to_json(), sort_keys=True, separators=(",", ":")) + "\n"

        try:
            with path.open("a", encoding="utf-8") as handle:
                handle.write(line)
        except Exception:
            # Best-effort: never block primary workflow.
            return None

        return path


def iter_activity_events(lines: Iterable[str]) -> Iterator[dict[str, Any]]:
    for line in lines:
        raw = line.strip()
        if not raw:
            continue
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            yield payload


def load_activity_events(ledger_dir: Path, *, limit: int | None = None) -> list[dict[str, Any]]:
    path = ledger_dir / DEFAULT_ACTIVITY_FILENAME
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    if limit is not None and limit > 0:
        lines = lines[-limit:]
    return list(iter_activity_events(lines))
