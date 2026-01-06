from __future__ import annotations

import sqlite3
from pathlib import Path

from motus.core.bootstrap import bootstrap_database_at_path
from motus.core.database_connection import reset_db_manager
from motus.core.layered_config import reset_config
from motus.motus_fs import create_motus_tree
from motus.scratch.store import ScratchStore


def _bootstrap_db(tmp_path: Path, monkeypatch) -> Path:
    db_path = tmp_path / "coordination.db"
    monkeypatch.setenv("MOTUS_DATABASE__PATH", str(db_path))
    reset_config()
    reset_db_manager()
    bootstrap_database_at_path(db_path)
    reset_db_manager()
    return db_path


def test_scratch_index_rebuild(tmp_path: Path) -> None:
    motus_dir = tmp_path / ".motus"
    create_motus_tree(motus_dir)

    store = ScratchStore(motus_dir)
    entry = store.create_entry(title="Scratch item", description="Test scratch")

    index_path = motus_dir / "scratch" / "index.json"
    index_path.write_text("{broken json")

    entries = store.list_entries()
    assert any(e.scratch_id == entry.scratch_id for e in entries)


def test_scratch_promote_to_roadmap(monkeypatch, tmp_path: Path) -> None:
    db_path = _bootstrap_db(tmp_path, monkeypatch)
    motus_dir = tmp_path / ".motus"
    create_motus_tree(motus_dir)

    store = ScratchStore(motus_dir)
    entry = store.create_entry(
        title="Scratch to roadmap",
        description="Promotion test",
        created_by="builder",
    )

    promoted = store.promote_to_roadmap(
        entry.scratch_id,
        phase_key="phase_012",
        item_type="work",
        agent_id="builder",
    )

    assert promoted.roadmap_id
    assert promoted.status == "promoted"

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rm_row = conn.execute(
        "SELECT id FROM roadmap_items WHERE id = ?",
        (promoted.roadmap_id,),
    ).fetchone()
    assert rm_row is not None

    dec_row = conn.execute(
        "SELECT id, decision_type FROM decisions WHERE work_id = ?",
        (promoted.roadmap_id,),
    ).fetchone()
    assert dec_row is not None
    assert dec_row["decision_type"] == "plan_committed"

    ev_row = conn.execute(
        "SELECT id, evidence_type FROM evidence WHERE work_id = ?",
        (promoted.roadmap_id,),
    ).fetchone()
    assert ev_row is not None
    assert ev_row["evidence_type"] == "document"

    conn.close()

    reloaded = store.load_entry(entry.scratch_id)
    assert reloaded.roadmap_id == promoted.roadmap_id
    assert reloaded.evidence_id == promoted.evidence_id
