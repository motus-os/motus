from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from motus.core.bootstrap import bootstrap_database_at_path
from motus.core.database_connection import reset_db_manager
from motus.core.layered_config import reset_config
from motus.scratch import ScratchStore


def _bootstrap_db(tmp_path: Path, monkeypatch) -> Path:
    db_path = tmp_path / "coordination.db"
    monkeypatch.setenv("MOTUS_DATABASE__PATH", str(db_path))
    reset_config()
    reset_db_manager()
    bootstrap_database_at_path(db_path)
    reset_db_manager()
    return db_path


def test_scratch_index_rebuild_on_corrupt_index(tmp_path: Path) -> None:
    root = tmp_path / ".motus" / "scratch"
    store = ScratchStore(root)
    entry = store.create_entry(title="Quick note", body="Remember to test.")

    index_path = root / "INDEX.json"
    index_path.write_text("{bad json", encoding="utf-8")

    rebuilt = store.load_index()
    assert any(e.entry_id == entry.entry_id for e in rebuilt.entries)

    payload = json.loads(index_path.read_text(encoding="utf-8"))
    assert payload.get("schema") == "motus.scratch.index.v1"


def test_scratch_promote_records_decision_and_evidence(monkeypatch, tmp_path: Path) -> None:
    db_path = _bootstrap_db(tmp_path, monkeypatch)
    monkeypatch.setenv("MC_AGENT_ID", "tester")

    root = tmp_path / ".motus" / "scratch"
    store = ScratchStore(root)
    entry = store.create_entry(title="Roadmap idea", body="Add scratch promotion.")

    result = store.promote_to_roadmap(entry.entry_id, phase_key="phase_h")

    updated = store.load_entry(entry.entry_id)
    assert updated.status == "promoted"
    assert updated.roadmap is not None
    assert updated.roadmap.item_id == result.roadmap_id

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    rm_row = conn.execute(
        "SELECT id, title FROM roadmap_items WHERE id = ?",
        (result.roadmap_id,),
    ).fetchone()
    assert rm_row is not None

    decision_row = conn.execute(
        "SELECT decision_type, work_id FROM decisions WHERE work_id = ?",
        (result.roadmap_id,),
    ).fetchone()
    assert decision_row is not None
    assert decision_row["decision_type"] == "plan_committed"

    evidence_row = conn.execute(
        "SELECT evidence_type, uri, work_id FROM evidence WHERE work_id = ?",
        (result.roadmap_id,),
    ).fetchone()
    assert evidence_row is not None
    assert evidence_row["evidence_type"] == "document"
    assert evidence_row["uri"].startswith("scratch:")

    conn.close()
