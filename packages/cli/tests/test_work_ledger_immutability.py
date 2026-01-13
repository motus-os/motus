from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

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


def _seed_work_item(conn: sqlite3.Connection, work_id: str, step_id: str) -> None:
    conn.execute(
        """
        INSERT INTO roadmap_items (id, phase_key, title, created_by)
        VALUES (?, ?, ?, ?)
        """,
        (work_id, "phase_f", f"Work item {work_id}", "unit-test"),
    )
    conn.execute(
        """
        INSERT INTO work_steps (id, work_id, status, owner, sequence)
        VALUES (?, ?, ?, ?, ?)
        """,
        (step_id, work_id, "in_progress", "agent-1", 1),
    )


def test_work_artifacts_are_immutable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = _bootstrap_db(tmp_path, monkeypatch)
    conn = sqlite3.connect(db_path)

    _seed_work_item(conn, "RI-IMM-001", "STEP-IMM-001")
    conn.execute(
        """
        INSERT INTO work_artifacts (
            id, artifact_type, source_ref, hash, created_by, work_id, step_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "artifact-1",
            "evidence",
            "evidence:artifact-1",
            "hash",
            "agent-1",
            "RI-IMM-001",
            "STEP-IMM-001",
        ),
    )
    conn.commit()

    with pytest.raises(sqlite3.Error) as excinfo:
        conn.execute(
            "UPDATE work_artifacts SET source_ref = ? WHERE id = ?",
            ("evidence:updated", "artifact-1"),
        )
    assert "KERNEL: Work artifacts are immutable" in str(excinfo.value)

    with pytest.raises(sqlite3.Error) as excinfo:
        conn.execute("DELETE FROM work_artifacts WHERE id = ?", ("artifact-1",))
    assert "KERNEL: Work artifacts cannot be deleted" in str(excinfo.value)

    conn.close()


def test_gate_outcomes_are_immutable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = _bootstrap_db(tmp_path, monkeypatch)
    conn = sqlite3.connect(db_path)

    _seed_work_item(conn, "RI-IMM-002", "STEP-IMM-002")
    conn.execute(
        """
        INSERT INTO gate_outcomes (id, gate_id, result, decided_by, work_id, step_id)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        ("gate-1", "GATE-TEST-001", "pass", "agent-1", "RI-IMM-002", "STEP-IMM-002"),
    )
    conn.commit()

    with pytest.raises(sqlite3.Error) as excinfo:
        conn.execute(
            "UPDATE gate_outcomes SET result = ? WHERE id = ?",
            ("fail", "gate-1"),
        )
    assert "KERNEL: Gate outcomes are immutable" in str(excinfo.value)

    with pytest.raises(sqlite3.Error) as excinfo:
        conn.execute("DELETE FROM gate_outcomes WHERE id = ?", ("gate-1",))
    assert "KERNEL: Gate outcomes cannot be deleted" in str(excinfo.value)

    conn.close()
