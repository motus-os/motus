from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from motus.coordination.gate_outcomes import persist_gate_outcome
from motus.core.bootstrap import bootstrap_database_at_path
from motus.core.database_connection import reset_db_manager
from motus.core.layered_config import reset_config


def _bootstrap_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    db_path = tmp_path / "coordination.db"
    monkeypatch.setenv("MOTUS_DATABASE__PATH", str(db_path))
    reset_config()
    reset_db_manager()
    bootstrap_database_at_path(db_path)
    reset_db_manager()
    return db_path


def test_persist_gate_outcome_inserts_row(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = _bootstrap_db(tmp_path, monkeypatch)

    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        INSERT INTO roadmap_items (id, phase_key, title, created_by)
        VALUES (?, ?, ?, ?)
        """,
        ("RI-TEST-001", "phase_f", "Test Work Item", "unit-test"),
    )
    conn.commit()
    conn.close()

    persisted = persist_gate_outcome(
        gate_id="GATE-TEST-001",
        status="pass",
        work_id="RI-TEST-001",
        decided_by="agent-1",
        reason="unit-test",
    )

    assert persisted is True

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        """
        SELECT gate_id, result, reason, decided_by, work_id, step_id
        FROM gate_outcomes
        """
    ).fetchone()
    conn.close()

    assert row is not None
    assert row["gate_id"] == "GATE-TEST-001"
    assert row["result"] == "pass"
    assert row["reason"] == "unit-test"
    assert row["decided_by"] == "agent-1"
    assert row["work_id"] == "RI-TEST-001"
    assert row["step_id"] is None
