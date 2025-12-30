from __future__ import annotations

import json
from dataclasses import replace

from motus.coordination.schemas import (
    WORK_BATCH_SCHEMA,
    ReconciliationReport,
    WorkBatch,
    WorkItem,
)

from .batch_models import (
    InvalidBatchTransitionError,
    ReconciliationError,
    _BatchStorage,
    _compute_batch_hash,
    _utcnow,
)


class BatchCoordinator(_BatchStorage):
    def create_batch(
        self,
        work_items: list[str],
        expected_artifacts: list[str],
        *,
        batch_type: str = "CR_GROUP",
        description: str = "",
        created_by: str = "unknown",
        agent_id: str = "unknown",
        session_id: str | None = None,
    ) -> WorkBatch:
        now = _utcnow()
        seq = self._next_sequence()
        batch_id = f"wb-{now.date().isoformat()}-{seq:04d}"
        prev = self._latest_batch_hash()
        prev_hash = prev[1] if prev is not None else None
        batch = WorkBatch(
            schema=WORK_BATCH_SCHEMA,
            batch_id=batch_id,
            batch_type=batch_type,
            description=description,
            status="DRAFT",
            created_at=now,
            created_by=created_by,
            work_items=[WorkItem(work_item_id=i, status="PENDING") for i in work_items],
            expected_artifacts=sorted({p for p in expected_artifacts if str(p).strip()}),
            reconciliation=None,
            batch_hash="",
            prev_batch_hash=prev_hash,
            sequence_number=seq,
        )
        payload = batch.to_json()
        batch = replace(batch, batch_hash=_compute_batch_hash(payload))
        self._write_active(batch)
        self._audit.emit(
            "BATCH_CREATED",
            {"batch_id": batch.batch_id, "status": batch.status},
            task_id=batch.batch_id,
            agent_id=agent_id,
            session_id=session_id,
        )
        return batch

    def start_batch(self, batch_id: str, *, agent_id: str = "unknown", session_id: str | None = None) -> WorkBatch:
        batch = self._load_batch(batch_id)
        self._transition(batch, to_status="EXECUTING", agent_id=agent_id, session_id=session_id)
        return self._load_batch(batch_id)

    def update_work_item(
        self,
        batch_id: str,
        work_item_id: str,
        status: str,
        *,
        agent_id: str = "unknown",
        session_id: str | None = None,
    ) -> WorkBatch:
        batch = self._load_batch(batch_id)
        items = [
            (replace(item, status=status) if item.work_item_id == work_item_id else item)
            for item in batch.work_items
        ]
        updated = replace(batch, work_items=items)
        updated = self._rehash(updated)
        self._write_active(updated)
        self._audit.emit(
            "BATCH_WORK_ITEM_UPDATED",
            {"batch_id": batch_id, "work_item_id": work_item_id, "status": status},
            task_id=batch_id,
            agent_id=agent_id,
            session_id=session_id,
        )
        return updated

    def add_produced_artifact(
        self,
        batch_id: str,
        artifact_path: str,
        *,
        agent_id: str = "unknown",
        session_id: str | None = None,
    ) -> WorkBatch:
        batch = self._load_batch(batch_id)
        current = set()
        if batch.reconciliation is not None:
            current = set(batch.reconciliation.produced_artifacts)
        current.add(str(artifact_path))
        report = self._compute_reconciliation(batch.expected_artifacts, sorted(current))
        updated = replace(batch, reconciliation=report)
        updated = self._rehash(updated)
        self._write_active(updated)
        self._audit.emit(
            "BATCH_ARTIFACT_PRODUCED",
            {"batch_id": batch_id, "artifact_path": artifact_path},
            task_id=batch_id,
            agent_id=agent_id,
            session_id=session_id,
        )
        return updated

    def verify_batch(
        self, batch_id: str, *, agent_id: str = "unknown", session_id: str | None = None
    ) -> ReconciliationReport:
        batch = self._load_batch(batch_id)
        self._transition(batch, to_status="VERIFYING", agent_id=agent_id, session_id=session_id)
        batch = self._load_batch(batch_id)
        produced = []
        if batch.reconciliation is not None:
            produced = list(batch.reconciliation.produced_artifacts)
        report = self._compute_reconciliation(batch.expected_artifacts, produced)
        updated = replace(batch, reconciliation=report)
        updated = self._rehash(updated)
        self._write_active(updated)
        self._audit.emit(
            "BATCH_VERIFIED",
            {"batch_id": batch_id, "balanced": report.balanced},
            task_id=batch_id,
            agent_id=agent_id,
            session_id=session_id,
        )
        return report

    def complete_batch(self, batch_id: str, *, agent_id: str = "unknown", session_id: str | None = None) -> WorkBatch:
        batch = self._load_batch(batch_id)
        if batch.status != "VERIFYING":
            raise InvalidBatchTransitionError(batch_id, batch.status, "COMPLETED")
        if batch.reconciliation is None or not batch.reconciliation.balanced:
            raise ReconciliationError(batch_id, batch.reconciliation or self._compute_reconciliation([], []))
        updated = replace(batch, status="COMPLETED")
        updated = self._rehash(updated)
        self._write_active(updated)
        self._archive_closed(updated)
        self._audit.emit(
            "BATCH_STATE_CHANGED",
            {"batch_id": batch_id, "from_status": batch.status, "to_status": "COMPLETED"},
            task_id=batch.batch_id,
            agent_id=agent_id,
            session_id=session_id,
        )
        return updated

    def fail_batch(
        self,
        batch_id: str,
        reason: str,
        *,
        agent_id: str = "unknown",
        session_id: str | None = None,
    ) -> WorkBatch:
        batch = self._load_batch(batch_id)
        updated = self._transition(batch, to_status="FAILED", agent_id=agent_id, session_id=session_id)
        payload = {"batch_id": batch_id, "reason": reason}
        self._audit.emit(
            "BATCH_FAILED",
            payload,
            task_id=batch_id,
            agent_id=agent_id,
            session_id=session_id,
        )
        self._archive_closed(updated)
        return updated

    def list_batches(self, *, include_closed: bool = False) -> list[WorkBatch]:
        batches: list[WorkBatch] = []
        if self._active_dir.exists():
            for path in sorted(self._active_dir.glob("wb-*.json")):
                batches.append(WorkBatch.from_json(json.loads(path.read_text(encoding="utf-8"))))
        if include_closed and self._closed_dir.exists():
            for path in sorted(self._closed_dir.rglob("wb-*.json")):
                batches.append(WorkBatch.from_json(json.loads(path.read_text(encoding="utf-8"))))
        batches.sort(key=lambda b: b.sequence_number)
        return batches
