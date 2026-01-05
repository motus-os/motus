from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from motus.commands.audit_cmd import audit_add_command, audit_promote_command
from motus.core.bootstrap import bootstrap_database_at_path
from motus.core.database_connection import reset_db_manager


def _bootstrap_db(tmp_path: Path, monkeypatch) -> Path:
    db_path = tmp_path / "coordination.db"
    monkeypatch.setenv("MOTUS_DATABASE__PATH", str(db_path))
    reset_db_manager()
    bootstrap_database_at_path(db_path)
    reset_db_manager()
    return db_path


def test_audit_add_and_promote(monkeypatch, tmp_path: Path) -> None:
    db_path = _bootstrap_db(tmp_path, monkeypatch)

    add_args = SimpleNamespace(
        title="Cache audit",
        description="Unbounded cache growth",
        severity="high",
        evidence=["file://evidence.txt"],
        json=True,
    )
    assert audit_add_command(add_args) == 0

    import sqlite3

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT resource_id, new_value FROM audit_log WHERE resource_type = ? ORDER BY id DESC LIMIT 1",
        ("audit_finding",),
    ).fetchone()
    assert row is not None
    finding_id = row["resource_id"]
    payload = json.loads(row["new_value"])
    assert payload["title"] == "Cache audit"

    promote_cr_args = SimpleNamespace(
        finding_id=finding_id,
        cr=True,
        roadmap=False,
        phase="phase_h",
        item_type="work",
        title=None,
        description=None,
        cr_id=None,
        json=False,
    )
    assert audit_promote_command(promote_cr_args) == 0

    cr_row = conn.execute(
        "SELECT id, description FROM change_requests WHERE description LIKE ? ORDER BY created_at DESC LIMIT 1",
        (f"%AuditFinding:{finding_id}%",),
    ).fetchone()
    assert cr_row is not None
    cr_id = cr_row["id"]

    promote_rm_args = SimpleNamespace(
        finding_id=finding_id,
        cr=False,
        roadmap=True,
        phase="phase_h",
        item_type="work",
        title=None,
        description=None,
        cr_id=cr_id,
        json=False,
    )
    assert audit_promote_command(promote_rm_args) == 0

    rm_row = conn.execute(
        "SELECT id, cr_id FROM roadmap_items WHERE cr_id = ? ORDER BY created_at DESC LIMIT 1",
        (cr_id,),
    ).fetchone()
    assert rm_row is not None
    assert rm_row["cr_id"] == cr_id

    conn.close()
