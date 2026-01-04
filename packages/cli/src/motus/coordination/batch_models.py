# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from motus.atomic_io import atomic_write_json, atomic_write_text
from motus.coordination.audit import AuditLog
from motus.coordination.schemas import ReconciliationReport, WorkBatch
from motus.file_lock import FileLockError, file_lock


class BatchCoordinatorError(Exception):
    pass
class BatchNotFoundError(BatchCoordinatorError):
    def __init__(self, batch_id: str) -> None:
        super().__init__(f"batch not found: {batch_id}")
        self.batch_id = batch_id
class InvalidBatchTransitionError(BatchCoordinatorError):
    def __init__(self, batch_id: str, from_status: str, to_status: str) -> None:
        super().__init__(f"invalid batch transition: {batch_id} {from_status} -> {to_status}")
        self.batch_id = batch_id
        self.from_status = from_status
        self.to_status = to_status
class ReconciliationError(BatchCoordinatorError):
    def __init__(self, batch_id: str, report: ReconciliationReport) -> None:
        super().__init__(f"batch reconciliation failed: {batch_id}")
        self.batch_id = batch_id
        self.report = report


_LOCK_TIMEOUT_SECONDS = 5.0


ALLOWED_STATUS_TRANSITIONS: dict[str, set[str]] = {
    "DRAFT": {"EXECUTING", "CANCELLED"},
    "EXECUTING": {"VERIFYING", "FAILED"},
    "VERIFYING": {"COMPLETED", "FAILED"},
    "COMPLETED": set(),
    "FAILED": {"REVERSED"},
    "REVERSED": set(),
    "CANCELLED": set(),
}

def _utcnow() -> datetime:
    return datetime.now(timezone.utc)

def _canonical_json_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")

def _compute_batch_hash(payload: dict[str, Any]) -> str:
    material = dict(payload)
    material.pop("batch_hash", None)
    digest = hashlib.sha256(_canonical_json_bytes(material)).hexdigest()
    return f"sha256:{digest}"


class _BatchStorage:
    def __init__(self, root_dir: str | Path) -> None:
        self._root = Path(root_dir)
        self._active_dir = self._root / "active"
        self._closed_dir = self._root / "closed"
        self._sequence_path = self._root / "SEQUENCE"
        self._audit = AuditLog(self._root.parent / "ledger")

    def _batch_path_active(self, batch_id: str) -> Path:
        return self._active_dir / f"{batch_id}.json"

    def _batch_path_closed(self, batch_id: str, *, created_at: datetime) -> Path:
        month = created_at.strftime("%Y-%m")
        return self._closed_dir / month / f"{batch_id}.json"

    def _next_sequence(self) -> int:
        self._root.mkdir(parents=True, exist_ok=True)
        try:
            with file_lock(self._sequence_path, timeout=_LOCK_TIMEOUT_SECONDS):
                current = 0
                try:
                    text = self._sequence_path.read_text(encoding="utf-8").strip()
                    if text:
                        current = int(text)
                except FileNotFoundError:
                    current = 0
                next_value = current + 1
                atomic_write_text(self._sequence_path, f"{next_value}\n")
                return next_value
        except FileLockError as exc:
            raise BatchCoordinatorError(
                f"failed to lock batch sequence file: {self._sequence_path}"
            ) from exc

    def _find_any_batch_path(self, batch_id: str) -> Path | None:
        active = self._batch_path_active(batch_id)
        if active.exists():
            return active
        for path in sorted(self._closed_dir.rglob(f"{batch_id}.json")):
            if path.is_file():
                return path
        return None

    def _load_batch(self, batch_id: str) -> WorkBatch:
        path = self._find_any_batch_path(batch_id)
        if path is None:
            raise BatchNotFoundError(batch_id)
        payload = json.loads(path.read_text(encoding="utf-8"))
        return WorkBatch.from_json(payload)

    def _write_active(self, batch: WorkBatch) -> None:
        self._active_dir.mkdir(parents=True, exist_ok=True)
        atomic_write_json(self._batch_path_active(batch.batch_id), batch.to_json())

    def _archive_closed(self, batch: WorkBatch) -> None:
        src = self._batch_path_active(batch.batch_id)
        dest = self._batch_path_closed(batch.batch_id, created_at=batch.created_at)
        dest.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_json(dest, batch.to_json())
        if src.exists():
            try:
                src.unlink()
            except OSError:
                pass

    def _latest_batch_hash(self) -> tuple[int, str] | None:
        candidates: list[tuple[int, str]] = []
        if self._active_dir.exists():
            for path in self._active_dir.glob("wb-*.json"):
                try:
                    payload = json.loads(path.read_text(encoding="utf-8"))
                    candidates.append(
                        (int(payload.get("sequence_number", 0)), str(payload.get("batch_hash", "")))
                    )
                except Exception:
                    continue
        if self._closed_dir.exists():
            for path in self._closed_dir.rglob("wb-*.json"):
                try:
                    payload = json.loads(path.read_text(encoding="utf-8"))
                    candidates.append(
                        (int(payload.get("sequence_number", 0)), str(payload.get("batch_hash", "")))
                    )
                except Exception:
                    continue
        candidates = [(seq, h) for (seq, h) in candidates if seq > 0 and h]
        if not candidates:
            return None
        candidates.sort(key=lambda t: t[0])
        return candidates[-1]

    def _rehash(self, batch: WorkBatch) -> WorkBatch:
        payload = batch.to_json()
        return replace(batch, batch_hash=_compute_batch_hash(payload))

    def _transition(self, batch: WorkBatch, *, to_status: str, agent_id: str, session_id: str | None) -> WorkBatch:
        from_status = batch.status
        allowed = ALLOWED_STATUS_TRANSITIONS.get(from_status, set())
        if to_status not in allowed:
            raise InvalidBatchTransitionError(batch.batch_id, from_status, to_status)
        updated = replace(batch, status=to_status)
        updated = self._rehash(updated)
        self._write_active(updated)
        self._audit.emit(
            "BATCH_STATE_CHANGED",
            {"batch_id": batch.batch_id, "from_status": from_status, "to_status": to_status},
            task_id=batch.batch_id,
            agent_id=agent_id,
            session_id=session_id,
        )
        return updated

    def _compute_reconciliation(self, expected: Iterable[str], produced: Iterable[str]) -> ReconciliationReport:
        expected_set = {str(p) for p in expected if str(p).strip()}
        produced_set = {str(p) for p in produced if str(p).strip()}
        missing = sorted(expected_set - produced_set)
        unexpected = sorted(produced_set - expected_set)
        produced_sorted = sorted(produced_set)
        balanced = len(missing) == 0 and len(unexpected) == 0
        return ReconciliationReport(
            expected_count=len(expected_set),
            produced_count=len(produced_set),
            produced_artifacts=produced_sorted,
            missing_artifacts=missing,
            unexpected_artifacts=unexpected,
            balanced=balanced,
        )
