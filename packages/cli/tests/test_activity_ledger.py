# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

from __future__ import annotations

import json
from pathlib import Path

from motus.observability.activity import ActivityLedger, load_activity_events


def test_activity_ledger_emits_event(tmp_path: Path, monkeypatch) -> None:
    ledger_dir = tmp_path / "ledger"
    monkeypatch.setenv("MOTUS_ACTIVITY_DIR", str(ledger_dir))

    ledger = ActivityLedger()
    path = ledger.emit(
        actor="test",
        category="cli",
        action="invoke",
        subject={"command": "activity"},
        context={"note": "test"},
    )

    assert path is not None
    assert path.exists()
    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1

    payload = json.loads(lines[0])
    assert payload["schema"] == "motus.activity.v1"
    assert payload["category"] == "cli"
    assert payload["action"] == "invoke"
    assert payload["subject"]["command"] == "activity"


def test_load_activity_events_respects_limit(tmp_path: Path, monkeypatch) -> None:
    ledger_dir = tmp_path / "ledger"
    monkeypatch.setenv("MOTUS_ACTIVITY_DIR", str(ledger_dir))

    ledger = ActivityLedger()
    for idx in range(3):
        ledger.emit(
            actor="test",
            category="cli",
            action="invoke",
            subject={"command": f"cmd-{idx}"},
        )

    events = load_activity_events(ledger_dir, limit=2)
    assert len(events) == 2
