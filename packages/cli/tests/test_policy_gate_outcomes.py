from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from motus.core.bootstrap import bootstrap_database_at_path
from motus.core.database_connection import reset_db_manager
from motus.core.layered_config import reset_config
from motus.policy.load import load_vault_policy
from motus.policy.loader import compute_gate_plan
from motus.policy.runner import run_gate_plan


def _fixture_dir() -> Path:
    return Path(__file__).parent / "fixtures" / "vault_policy"


def _write_vault_tree(tmp_path: Path) -> Path:
    fixtures = _fixture_dir()
    registry_src = fixtures / "registry.json"
    gates_src = fixtures / "gates.json"
    profiles_src = fixtures / "profiles.json"
    evidence_schema_src = fixtures / "evidence-manifest.schema.json"

    registry_dest = tmp_path / "core/best-practices/skill-packs/registry.json"
    registry_dest.parent.mkdir(parents=True, exist_ok=True)
    registry_dest.write_text(registry_src.read_text(encoding="utf-8"), encoding="utf-8")

    gates_dest = tmp_path / "core/best-practices/gates.json"
    gates_dest.parent.mkdir(parents=True, exist_ok=True)
    gates_dest.write_text(gates_src.read_text(encoding="utf-8"), encoding="utf-8")

    profiles_dest = tmp_path / "core/best-practices/profiles/profiles.json"
    profiles_dest.parent.mkdir(parents=True, exist_ok=True)
    profiles_dest.write_text(profiles_src.read_text(encoding="utf-8"), encoding="utf-8")

    evidence_schema_dest = (
        tmp_path / "core/best-practices/control-plane/evidence-manifest.schema.json"
    )
    evidence_schema_dest.parent.mkdir(parents=True, exist_ok=True)
    evidence_schema_dest.write_text(
        evidence_schema_src.read_text(encoding="utf-8"), encoding="utf-8"
    )

    data = json.loads(gates_dest.read_text(encoding="utf-8"))
    for gate in data.get("gates", []):
        gate["kind"] = "intake"
    gates_dest.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")

    return tmp_path


def _bootstrap_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    db_path = tmp_path / "coordination.db"
    monkeypatch.setenv("MOTUS_DATABASE__PATH", str(db_path))
    reset_config()
    reset_db_manager()
    bootstrap_database_at_path(db_path)
    reset_db_manager()
    return db_path


def test_policy_run_persists_gate_outcomes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    vault_dir = _write_vault_tree(tmp_path / "vault")
    db_path = _bootstrap_db(tmp_path, monkeypatch)

    work_id = "RI-POLICY-001"
    step_id = "STEP-POLICY-001"

    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        INSERT INTO roadmap_items (id, phase_key, title, created_by)
        VALUES (?, ?, ?, ?)
        """,
        (work_id, "phase_f", "Policy gate persistence", "unit-test"),
    )
    conn.execute(
        """
        INSERT INTO work_steps (id, work_id, status, owner, sequence)
        VALUES (?, ?, ?, ?, ?)
        """,
        (step_id, work_id, "in_progress", "agent-1", 1),
    )
    conn.commit()
    conn.close()

    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    (repo_dir / "README.md").write_text("Policy run test", encoding="utf-8")

    policy = load_vault_policy(vault_dir)
    plan = compute_gate_plan(
        changed_files=["README.md"],
        policy=policy,
        profile_id="personal",
        pack_cap=None,
    )

    result = run_gate_plan(
        plan=plan,
        declared_files=["README.md"],
        declared_files_source="files",
        repo_dir=repo_dir,
        vault_dir=vault_dir,
        evidence_dir=tmp_path / "evidence",
        policy=policy,
        work_id=work_id,
        step_id=step_id,
        decided_by="agent-1",
    )

    assert result.exit_code == 0

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT gate_id, result, work_id, step_id, decided_by, policy_ref
        FROM gate_outcomes
        WHERE work_id = ?
        """,
        (work_id,),
    ).fetchall()
    conn.close()

    assert len(rows) == len(plan.gates)
    assert {row["gate_id"] for row in rows} == set(plan.gates)
    assert all(row["result"] == "pass" for row in rows)
    assert all(row["step_id"] == step_id for row in rows)
    assert all(row["decided_by"] == "agent-1" for row in rows)
    assert all(str(row["policy_ref"]).startswith("gates:") for row in rows)
