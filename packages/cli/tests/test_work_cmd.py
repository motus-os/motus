from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from motus.commands.work_cmd import cmd_work_list, cmd_work_status
from motus.core.bootstrap import bootstrap_database_at_path
from motus.core.database_connection import reset_db_manager
from motus.core.layered_config import reset_config
from motus.api import WorkCompiler
from motus.coordination.schemas import ClaimedResource


def _bootstrap_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    db_path = tmp_path / "coordination.db"
    monkeypatch.setenv("MOTUS_DATABASE__PATH", str(db_path))
    reset_config()
    reset_db_manager()
    bootstrap_database_at_path(db_path)
    reset_db_manager()
    return db_path


def _ensure_leases_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS coordination_leases (
            lease_id TEXT PRIMARY KEY,
            owner_agent_id TEXT NOT NULL,
            mode TEXT NOT NULL,
            resources TEXT NOT NULL,
            issued_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            heartbeat_deadline TEXT NOT NULL,
            snapshot_id TEXT NOT NULL,
            policy_version TEXT NOT NULL,
            lens_digest TEXT NOT NULL,
            work_id TEXT,
            attempt_id TEXT,
            status TEXT NOT NULL DEFAULT 'active',
            outcome TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_coordination_leases_status ON coordination_leases(status)"
    )


def test_work_list_filters_active(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db_path = _bootstrap_db(tmp_path, monkeypatch)

    now = datetime.now(timezone.utc)
    active_expires = now + timedelta(hours=1)
    expired_expires = now - timedelta(hours=1)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    _ensure_leases_table(conn)

    conn.execute(
        """
        INSERT INTO coordination_leases (
            lease_id, owner_agent_id, mode, resources, issued_at, expires_at,
            heartbeat_deadline, snapshot_id, policy_version, lens_digest,
            work_id, attempt_id, status, outcome, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "lease-active",
            "agent-1",
            "write",
            "[]",
            now.isoformat().replace("+00:00", "Z"),
            active_expires.isoformat().replace("+00:00", "Z"),
            active_expires.isoformat().replace("+00:00", "Z"),
            "snap",
            "v1",
            "digest",
            "RI-TEST-001",
            None,
            "active",
            None,
            now.isoformat().replace("+00:00", "Z"),
            now.isoformat().replace("+00:00", "Z"),
        ),
    )
    conn.execute(
        """
        INSERT INTO coordination_leases (
            lease_id, owner_agent_id, mode, resources, issued_at, expires_at,
            heartbeat_deadline, snapshot_id, policy_version, lens_digest,
            work_id, attempt_id, status, outcome, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "lease-expired",
            "agent-2",
            "write",
            "[]",
            now.isoformat().replace("+00:00", "Z"),
            expired_expires.isoformat().replace("+00:00", "Z"),
            expired_expires.isoformat().replace("+00:00", "Z"),
            "snap",
            "v1",
            "digest",
            "RI-TEST-002",
            None,
            "expired",
            None,
            now.isoformat().replace("+00:00", "Z"),
            now.isoformat().replace("+00:00", "Z"),
        ),
    )
    conn.commit()
    conn.close()

    args = SimpleNamespace(json=True, all=False)
    assert cmd_work_list(args) == 0

    captured = capsys.readouterr().out
    payload = json.loads(captured)
    assert payload["count"] == 1
    assert payload["items"][0]["lease_id"] == "lease-active"


def test_work_list_all_includes_expired(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db_path = _bootstrap_db(tmp_path, monkeypatch)

    now = datetime.now(timezone.utc)
    expires_at = now - timedelta(hours=1)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    _ensure_leases_table(conn)

    conn.execute(
        """
        INSERT INTO coordination_leases (
            lease_id, owner_agent_id, mode, resources, issued_at, expires_at,
            heartbeat_deadline, snapshot_id, policy_version, lens_digest,
            work_id, attempt_id, status, outcome, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "lease-expired",
            "agent-2",
            "write",
            "[]",
            now.isoformat().replace("+00:00", "Z"),
            expires_at.isoformat().replace("+00:00", "Z"),
            expires_at.isoformat().replace("+00:00", "Z"),
            "snap",
            "v1",
            "digest",
            "RI-TEST-003",
            None,
            "expired",
            None,
            now.isoformat().replace("+00:00", "Z"),
            now.isoformat().replace("+00:00", "Z"),
        ),
    )
    conn.commit()
    conn.close()

    args = SimpleNamespace(json=True, all=True)
    assert cmd_work_list(args) == 0

    captured = capsys.readouterr().out
    payload = json.loads(captured)
    assert payload["count"] == 1
    assert payload["items"][0]["lease_id"] == "lease-expired"


def test_work_status_reads_persisted_records(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    db_path = _bootstrap_db(tmp_path, monkeypatch)

    compiler = WorkCompiler()
    result = compiler.claim_work(
        task_id="ADHOC-STATUS-001",
        resources=[ClaimedResource(type="file", path="README.md")],
        intent="Status query",
        agent_id="agent-1",
    )
    assert result.decision.decision == "GRANTED"

    lease_id = result.lease.lease_id
    compiler.put_outcome(lease_id, "file", path="output.txt")
    compiler.record_evidence(
        lease_id,
        "test_result",
        test_results={"passed": 1, "failed": 0, "skipped": 0},
    )
    compiler.record_decision(lease_id, "Approve change")

    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        INSERT INTO gate_outcomes (id, gate_id, result, decided_by, work_id)
        VALUES (?, ?, ?, ?, ?)
        """,
        ("gate-1", "GATE-TEST-001", "pass", "agent-1", result.lease.work_id),
    )
    conn.commit()
    conn.close()

    args = SimpleNamespace(json=True, lease_id=lease_id)
    assert cmd_work_status(args) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["lease_id"] == lease_id
    assert len(payload["outcomes"]) == 1
    assert payload["outcomes"][0]["outcome_type"] == "file"
    assert len(payload["evidence"]) == 1
    assert payload["evidence"][0]["evidence_type"] == "test_result"
    assert len(payload["decisions"]) == 1
    assert payload["decisions"][0]["decision"] == "Approve change"
    assert len(payload["gate_outcomes"]) == 1
    assert payload["gate_outcomes"][0]["gate_id"] == "GATE-TEST-001"
