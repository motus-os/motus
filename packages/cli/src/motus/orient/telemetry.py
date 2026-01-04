# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Local telemetry for Cached Orient.

This is workspace-local (stored under `.motus/state/orient/`) so that hit-rate
analytics are project-scoped and don't require the global coordination DB.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator, Literal

OrientResultKind = Literal["HIT", "MISS", "CONFLICT"]


def _utc_now_iso_z() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def orient_events_path(motus_dir: Path) -> Path:
    return motus_dir / "state" / "orient" / "events.jsonl"


@dataclass(frozen=True, slots=True)
class OrientTelemetryEvent:
    timestamp: str
    decision_type: str
    result: OrientResultKind
    standard_id: str | None = None
    layer: str | None = None

    def to_json(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "ts": self.timestamp,
            "decision_type": self.decision_type,
            "result": self.result,
        }
        if self.standard_id is not None:
            payload["standard_id"] = self.standard_id
        if self.layer is not None:
            payload["layer"] = self.layer
        return payload


def append_orient_event(
    motus_dir: Path,
    *,
    decision_type: str,
    result: OrientResultKind,
    standard_id: str | None,
    layer: str | None,
) -> Path:
    """Append a single orient decision event (best-effort).

    The write is an append-only JSONL line. We intentionally keep this separate
    from the coordination ledger to avoid mixing control-plane events with
    Cached Orient decision telemetry.
    """

    path = orient_events_path(motus_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    event = OrientTelemetryEvent(
        timestamp=_utc_now_iso_z(),
        decision_type=decision_type,
        result=result,
        standard_id=standard_id,
        layer=layer,
    )
    line = json.dumps(event.to_json(), separators=(",", ":"), sort_keys=True) + "\n"
    with path.open("a", encoding="utf-8") as f:
        f.write(line)
    return path


def iter_orient_events_from_lines(lines: Iterable[str]) -> Iterator[dict[str, Any]]:
    for line in lines:
        raw = line.strip()
        if not raw:
            continue
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict):
            continue
        yield payload


def iter_orient_events(motus_dir: Path) -> Iterator[dict[str, Any]]:
    path = orient_events_path(motus_dir)
    if not path.exists():
        return iter(())
    return iter_orient_events_from_lines(path.read_text(encoding="utf-8").splitlines())

