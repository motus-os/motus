from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from motus.api import WorkCompiler
from motus.coordination.schemas import ClaimedResource
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


def _insert_work_item(db_path: Path, work_id: str) -> None:
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        INSERT INTO roadmap_items (id, phase_key, title, created_by)
        VALUES (?, ?, ?, ?)
        """,
        (work_id, "phase_f", f"Work item {work_id}", "unit-test"),
    )
    conn.commit()
    conn.close()


@pytest.fixture
def wc(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[WorkCompiler, Path]:
    from motus.context_cache import ContextCache
    from motus.coordination.api import Coordinator
    from motus.coordination.api.lease_store import LeaseStore

    db_path = _bootstrap_db(tmp_path, monkeypatch)
    cache_path = tmp_path / "context_cache.db"

    lease_store = LeaseStore(db_path=str(db_path))
    context_cache = ContextCache(db_path=str(cache_path))
    coordinator = Coordinator(
        lease_store=lease_store,
        context_cache=context_cache,
        policy_version="v1.0.0",
    )
    return WorkCompiler(coordinator=coordinator), db_path


def test_claim_work_updates_work_item_and_creates_step(wc) -> None:
    compiler, db_path = wc
    work_id = "RI-LEDGER-001"
    _insert_work_item(db_path, work_id)

    result = compiler.claim_work(
        task_id=work_id,
        resources=[ClaimedResource(type="file", path="README.md")],
        intent="Verify ledger fields",
        agent_id="agent-1",
        work_mode="expanded",
        work_type="planning",
        routing_class="review",
        program_ref="PRG-001",
        scope=["policy", "docs"],
    )

    assert result.decision.decision == "GRANTED"

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        """
        SELECT mode, work_type, routing_class, program_ref, intent, scope,
               owner, claimed_at, lease_expires_at
        FROM roadmap_items
        WHERE id = ?
        """,
        (work_id,),
    ).fetchone()

    assert row is not None
    assert row["mode"] == "expanded"
    assert row["work_type"] == "planning"
    assert row["routing_class"] == "review"
    assert row["program_ref"] == "PRG-001"
    assert row["intent"] == "Verify ledger fields"
    assert json.loads(row["scope"]) == ["docs", "policy"]
    assert row["owner"] == "agent-1"
    assert row["claimed_at"]
    assert row["lease_expires_at"]

    step = conn.execute(
        """
        SELECT status, owner, sequence, action_type, ooda_tag
        FROM work_steps
        WHERE work_id = ?
        """,
        (work_id,),
    ).fetchone()
    conn.close()

    assert step is not None
    assert step["status"] == "in_progress"
    assert step["owner"] == "agent-1"
    assert step["sequence"] == 1
    assert step["action_type"] == "execute"
    assert step["ooda_tag"] == "act"


def test_record_evidence_and_decision_create_artifacts(wc) -> None:
    compiler, db_path = wc
    work_id = "RI-LEDGER-002"
    _insert_work_item(db_path, work_id)

    result = compiler.claim_work(
        task_id=work_id,
        resources=[ClaimedResource(type="file", path="README.md")],
        intent="Record evidence and decisions",
        agent_id="agent-1",
    )
    assert result.decision.decision == "GRANTED"
    lease_id = result.lease.lease_id

    evidence = compiler.record_evidence(
        lease_id,
        "test_result",
        test_results={"passed": 1, "failed": 0, "skipped": 0},
    )
    decision = compiler.record_decision(
        lease_id,
        "Approve change",
        rationale="Meets requirements",
    )

    assert evidence.accepted is True
    assert decision.accepted is True

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT artifact_type, source_ref, step_id
        FROM work_artifacts
        WHERE work_id = ?
        """,
        (work_id,),
    ).fetchall()
    conn.close()

    types = {row["artifact_type"] for row in rows}
    assert types == {"evidence", "decision_note"}
    assert all(row["step_id"] for row in rows)
