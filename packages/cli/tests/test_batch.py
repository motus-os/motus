from __future__ import annotations

import json
from pathlib import Path

import pytest

from motus.coordination.batch import BatchCoordinator, ReconciliationError


def _read_ledger_lines(root: Path) -> list[dict]:
    ledger = root.parent / "ledger"
    if not ledger.exists():
        return []
    items: list[dict] = []
    for path in sorted(ledger.glob("*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            items.append(json.loads(line))
    return items


def test_create_batch_starts_in_draft(tmp_path: Path) -> None:
    batches_dir = tmp_path / "batches"
    coord = BatchCoordinator(batches_dir)
    batch = coord.create_batch(
        work_items=["CR-test-1", "CR-test-2"],
        expected_artifacts=["foo.py", "bar.py"],
        created_by="agent-a",
        agent_id="agent-a",
    )
    assert batch.status == "DRAFT"
    assert batch.batch_id.startswith("wb-")
    assert batch.sequence_number >= 1
    assert batch.batch_hash.startswith("sha256:")


def test_start_batch_transitions_to_executing(tmp_path: Path) -> None:
    coord = BatchCoordinator(tmp_path / "batches")
    batch = coord.create_batch(work_items=["CR-test-1"], expected_artifacts=["foo.py"])
    started = coord.start_batch(batch.batch_id)
    assert started.status == "EXECUTING"


def test_verify_reports_missing_and_blocks_complete(tmp_path: Path) -> None:
    coord = BatchCoordinator(tmp_path / "batches")
    batch = coord.create_batch(work_items=["CR-test-1"], expected_artifacts=["foo.py", "bar.py"])
    coord.start_batch(batch.batch_id)
    coord.add_produced_artifact(batch.batch_id, "foo.py")

    report = coord.verify_batch(batch.batch_id)
    assert report.balanced is False
    assert report.missing_artifacts == ["bar.py"]

    with pytest.raises(ReconciliationError):
        coord.complete_batch(batch.batch_id)


def test_complete_archives_to_closed(tmp_path: Path) -> None:
    batches_dir = tmp_path / "batches"
    coord = BatchCoordinator(batches_dir)
    batch = coord.create_batch(work_items=["CR-test-1"], expected_artifacts=["foo.py"])
    coord.start_batch(batch.batch_id)
    coord.add_produced_artifact(batch.batch_id, "foo.py")
    report = coord.verify_batch(batch.batch_id)
    assert report.balanced is True

    completed = coord.complete_batch(batch.batch_id)
    assert completed.status == "COMPLETED"

    active_path = batches_dir / "active" / f"{batch.batch_id}.json"
    assert active_path.exists() is False
    closed_files = list((batches_dir / "closed").rglob(f"{batch.batch_id}.json"))
    assert len(closed_files) == 1


def test_hash_chain_links_batches(tmp_path: Path) -> None:
    coord = BatchCoordinator(tmp_path / "batches")
    a = coord.create_batch(work_items=["CR-a"], expected_artifacts=["a.py"])
    b = coord.create_batch(work_items=["CR-b"], expected_artifacts=["b.py"])
    assert b.prev_batch_hash == a.batch_hash


def test_emits_audit_events(tmp_path: Path) -> None:
    coord = BatchCoordinator(tmp_path / "batches")
    batch = coord.create_batch(work_items=["CR-a"], expected_artifacts=["a.py"], agent_id="agent-a")
    coord.start_batch(batch.batch_id, agent_id="agent-a")
    coord.add_produced_artifact(batch.batch_id, "a.py", agent_id="agent-a")
    coord.verify_batch(batch.batch_id, agent_id="agent-a")
    coord.complete_batch(batch.batch_id, agent_id="agent-a")

    events = _read_ledger_lines(tmp_path / "batches")
    types = {e.get("event_type") for e in events}
    assert "BATCH_CREATED" in types
    assert "BATCH_STATE_CHANGED" in types

