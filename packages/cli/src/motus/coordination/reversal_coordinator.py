# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from .reversal_types import VerificationResult
from .schemas import REVERSAL_BATCH_SCHEMA, CompensatingAction, ReversalBatch, ReversalItem
from .snapshot import SnapshotManager


class ReversalCoordinator:
    def __init__(
        self,
        reversal_dir: str | Path,
        batch_coordinator: object | None = None,  # Type will be BatchCoordinator when available
    ) -> None:
        self.reversal_dir = Path(reversal_dir)
        self.active_dir = self.reversal_dir / "active"
        self.closed_dir = self.reversal_dir / "closed"
        self.batch_coordinator = batch_coordinator
        self.active_dir.mkdir(parents=True, exist_ok=True)
        self.closed_dir.mkdir(parents=True, exist_ok=True)
        self.snapshot_manager = SnapshotManager(self.reversal_dir / "snapshots")
    def create_reversal(
        self,
        batch_id: str,
        reversal_type: str,
        reason: str,
        items: list[str] | None = None,
        created_by: str = "agent-unknown",
    ) -> ReversalBatch:
        reversal_id = self._generate_reversal_id()
        compensating_actions = self.get_compensating_actions(batch_id, items)
        items_to_reverse = self._build_reversal_items(compensating_actions, items)
        reversal_hash = self._compute_reversal_hash(reversal_id, batch_id)
        original_batch_hash = self._compute_batch_hash(batch_id)
        reversal = ReversalBatch(
            schema=REVERSAL_BATCH_SCHEMA,
            reversal_id=reversal_id,
            reverses_batch_id=batch_id,
            reversal_type=reversal_type,
            status="DRAFT",
            reason=reason,
            created_at=datetime.now(timezone.utc),
            created_by=created_by,
            items_to_reverse=items_to_reverse,
            compensating_actions_log=[],
            reversal_hash=reversal_hash,
            original_batch_hash=original_batch_hash,
        )
        self._save_reversal(reversal)
        return reversal

    def execute_reversal(self, reversal_id: str) -> ReversalBatch:
        reversal = self._load_reversal(reversal_id)
        if reversal is None:
            raise ValueError(f"Reversal not found: {reversal_id}")
        if reversal.status not in ("DRAFT", "FAILED"):
            raise ValueError(f"Cannot execute reversal in status: {reversal.status}")

        file_paths = self._extract_file_paths(reversal)
        self.snapshot_manager.capture_snapshot(reversal_id, file_paths)
        reversal = replace(reversal, status="EXECUTING")
        self._save_reversal(reversal)

        actions_log: list[CompensatingAction] = []
        failed = False
        compensating_actions = self.get_compensating_actions(reversal.reverses_batch_id)
        for action in compensating_actions:
            try:
                result = self._execute_compensating_action(action)
                actions_log.append(result)
                if result.result == "FAILED":
                    failed = True
                    break
            except Exception:
                failed_action = replace(
                    action,
                    executed_at=datetime.now(timezone.utc),
                    result="FAILED",
                )
                actions_log.append(failed_action)
                failed = True
                break

        final_status = "FAILED" if failed else "COMPLETED"
        reversal = replace(reversal, status=final_status, compensating_actions_log=actions_log)
        self._save_reversal(reversal)
        if final_status == "COMPLETED":
            self._move_to_closed(reversal)
        return reversal

    def get_compensating_actions(self, batch_id: str, items: list[str] | None = None) -> list[CompensatingAction]:
        action_id = "ca-001"
        return [
            CompensatingAction(
                action_id=action_id,
                action_type="BATCH_MARK_REVERSED",
                target=batch_id,
                executed_at=None,
                result=None,
                before_hash=None,
                after_hash=None,
            )
        ]

    def verify_reversal(self, reversal_id: str) -> VerificationResult:
        reversal = self._load_reversal(reversal_id)
        if reversal is None:
            return VerificationResult(
                success=False, message=f"Reversal not found: {reversal_id}", failed_actions=[]
            )
        if reversal.status != "COMPLETED":
            return VerificationResult(
                success=False,
                message=f"Reversal not completed (status: {reversal.status})",
                failed_actions=[],
            )

        failed_actions = [
            action.action_id for action in reversal.compensating_actions_log if action.result != "SUCCESS"
        ]
        if failed_actions:
            return VerificationResult(
                success=False,
                message=f"Some actions failed: {', '.join(failed_actions)}",
                failed_actions=failed_actions,
            )
        return VerificationResult(success=True, message="All actions completed successfully", failed_actions=[])

    def _generate_reversal_id(self) -> str:
        now = datetime.now(timezone.utc)
        date_str = now.strftime("%Y-%m-%d")
        existing = list(self.active_dir.glob(f"rev-{date_str}-*.json"))
        existing.extend(self.closed_dir.glob(f"**/rev-{date_str}-*.json"))
        sequence = len(existing) + 1
        return f"rev-{date_str}-{sequence:04d}"

    def _build_reversal_items(self, actions: list[CompensatingAction], work_items: list[str] | None) -> list[ReversalItem]:
        items = []
        for i, action in enumerate(actions):
            work_item_id = work_items[i] if work_items and i < len(work_items) else f"item-{i}"
            items.append(
                ReversalItem(
                    work_item_id=work_item_id,
                    original_status="COMPLETED",
                    compensating_action=action.action_type,
                    artifacts_to_remove=[],
                    status="PENDING",
                )
            )
        return items

    def _extract_file_paths(self, reversal: ReversalBatch) -> list[str]:
        return [
            path for item in reversal.items_to_reverse for path in item.artifacts_to_remove
        ]

    def _execute_compensating_action(self, action: CompensatingAction) -> CompensatingAction:
        return replace(
            action,
            executed_at=datetime.now(timezone.utc),
            result="SUCCESS",
            before_hash="sha256:before",
            after_hash="sha256:after",
        )

    def _compute_reversal_hash(self, reversal_id: str, batch_id: str) -> str:
        content = f"{reversal_id}:{batch_id}"
        return f"sha256:{hashlib.sha256(content.encode()).hexdigest()}"

    def _compute_batch_hash(self, batch_id: str) -> str:
        return f"sha256:{hashlib.sha256(batch_id.encode()).hexdigest()}"

    def _save_reversal(self, reversal: ReversalBatch) -> None:
        reversal_path = self.active_dir / f"{reversal.reversal_id}.json"
        with open(reversal_path, "w") as f:
            json.dump(reversal.to_json(), f, indent=2)

    def _load_reversal(self, reversal_id: str) -> ReversalBatch | None:
        active_path = self.active_dir / f"{reversal_id}.json"
        if active_path.exists():
            with open(active_path) as f:
                return ReversalBatch.from_json(json.load(f))
        for closed_file in self.closed_dir.glob(f"**/{reversal_id}.json"):
            with open(closed_file) as f:
                return ReversalBatch.from_json(json.load(f))
        return None

    def _move_to_closed(self, reversal: ReversalBatch) -> None:
        year_month = reversal.created_at.strftime("%Y-%m")
        closed_subdir = self.closed_dir / year_month
        closed_subdir.mkdir(parents=True, exist_ok=True)
        active_path = self.active_dir / f"{reversal.reversal_id}.json"
        closed_path = closed_subdir / f"{reversal.reversal_id}.json"
        if active_path.exists():
            active_path.rename(closed_path)
