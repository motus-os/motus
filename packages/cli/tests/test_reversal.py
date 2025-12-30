"""Tests for reversal coordination."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

import pytest

from motus.coordination.reversal import ReversalCoordinator
from motus.coordination.schemas import (
    REVERSAL_BATCH_SCHEMA,
    CompensatingAction,
    ReversalBatch,
)
from motus.coordination.snapshot import SnapshotManager


class TestSnapshotManager:
    """Test snapshot capture functionality."""

    def test_capture_snapshot_existing_file(self, tmp_path: Path) -> None:
        """Test capturing snapshot of existing file."""
        snapshot_dir = tmp_path / "snapshots"
        manager = SnapshotManager(snapshot_dir)

        # Create a test file
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        snapshot = manager.capture_snapshot("rev-2025-12-18-0001", [str(test_file)])

        assert snapshot.snapshot_id == "snap-2025-12-18-0001"
        assert snapshot.reversal_id == "rev-2025-12-18-0001"
        assert len(snapshot.file_states) == 1
        assert snapshot.file_states[0].path == str(test_file)
        assert snapshot.file_states[0].exists is True
        assert snapshot.file_states[0].hash.startswith("sha256:")

    def test_capture_snapshot_missing_file(self, tmp_path: Path) -> None:
        """Test capturing snapshot of non-existent file."""
        snapshot_dir = tmp_path / "snapshots"
        manager = SnapshotManager(snapshot_dir)

        missing_file = tmp_path / "missing.txt"

        snapshot = manager.capture_snapshot("rev-2025-12-18-0002", [str(missing_file)])

        assert len(snapshot.file_states) == 1
        assert snapshot.file_states[0].path == str(missing_file)
        assert snapshot.file_states[0].exists is False
        assert snapshot.file_states[0].hash == ""

    def test_get_snapshot(self, tmp_path: Path) -> None:
        """Test retrieving saved snapshot."""
        snapshot_dir = tmp_path / "snapshots"
        manager = SnapshotManager(snapshot_dir)

        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        # Create and save snapshot
        snapshot1 = manager.capture_snapshot("rev-2025-12-18-0003", [str(test_file)])

        # Load it back
        snapshot2 = manager.get_snapshot(snapshot1.snapshot_id)

        assert snapshot2 is not None
        assert snapshot2.snapshot_id == snapshot1.snapshot_id
        assert snapshot2.reversal_id == snapshot1.reversal_id
        assert len(snapshot2.file_states) == len(snapshot1.file_states)

    def test_get_snapshot_not_found(self, tmp_path: Path) -> None:
        """Test retrieving non-existent snapshot."""
        snapshot_dir = tmp_path / "snapshots"
        manager = SnapshotManager(snapshot_dir)

        snapshot = manager.get_snapshot("snap-nonexistent")
        assert snapshot is None


class TestReversalCoordinator:
    """Test reversal coordination functionality."""

    def test_create_reversal_full(self, tmp_path: Path) -> None:
        """Test creating a full reversal."""
        reversal_dir = tmp_path / "reversals"
        coordinator = ReversalCoordinator(reversal_dir)

        reversal = coordinator.create_reversal(
            batch_id="wb-2025-12-18-0001",
            reversal_type="FULL",
            reason="Testing full reversal",
            created_by="test-agent",
        )

        assert reversal.schema == REVERSAL_BATCH_SCHEMA
        assert re.match(r"^rev-\d{4}-\d{2}-\d{2}-\d{4}$", reversal.reversal_id)
        assert reversal.reverses_batch_id == "wb-2025-12-18-0001"
        assert reversal.reversal_type == "FULL"
        assert reversal.status == "DRAFT"
        assert reversal.reason == "Testing full reversal"
        assert reversal.created_by == "test-agent"
        assert len(reversal.compensating_actions_log) == 0

    def test_create_reversal_partial(self, tmp_path: Path) -> None:
        """Test creating a partial reversal."""
        reversal_dir = tmp_path / "reversals"
        coordinator = ReversalCoordinator(reversal_dir)

        reversal = coordinator.create_reversal(
            batch_id="wb-2025-12-18-0002",
            reversal_type="PARTIAL",
            reason="Partial reversal test",
            items=["CR-test-1"],
            created_by="test-agent",
        )

        assert reversal.reversal_type == "PARTIAL"
        assert reversal.status == "DRAFT"

    def test_create_reversal_saves_to_disk(self, tmp_path: Path) -> None:
        """Test that created reversal is saved to disk."""
        reversal_dir = tmp_path / "reversals"
        coordinator = ReversalCoordinator(reversal_dir)

        reversal = coordinator.create_reversal(
            batch_id="wb-2025-12-18-0003",
            reversal_type="FULL",
            reason="Test persistence",
        )

        # Check file exists
        reversal_file = reversal_dir / "active" / f"{reversal.reversal_id}.json"
        assert reversal_file.exists()

        # Check content
        with open(reversal_file) as f:
            data = json.load(f)
        assert data["reversal_id"] == reversal.reversal_id
        assert data["schema"] == REVERSAL_BATCH_SCHEMA

    def test_execute_reversal_success(self, tmp_path: Path) -> None:
        """Test successful reversal execution."""
        reversal_dir = tmp_path / "reversals"
        coordinator = ReversalCoordinator(reversal_dir)

        # Create reversal
        reversal = coordinator.create_reversal(
            batch_id="wb-2025-12-18-0004",
            reversal_type="FULL",
            reason="Test execution",
        )

        # Execute it
        result = coordinator.execute_reversal(reversal.reversal_id)

        assert result.status == "COMPLETED"
        assert len(result.compensating_actions_log) > 0
        # Should be moved to closed
        active_file = reversal_dir / "active" / f"{reversal.reversal_id}.json"
        assert not active_file.exists()

    def test_execute_reversal_creates_snapshot(self, tmp_path: Path) -> None:
        """Test that execution creates a pre-reversal snapshot."""
        reversal_dir = tmp_path / "reversals"
        coordinator = ReversalCoordinator(reversal_dir)

        reversal = coordinator.create_reversal(
            batch_id="wb-2025-12-18-0005",
            reversal_type="FULL",
            reason="Test snapshot",
        )

        coordinator.execute_reversal(reversal.reversal_id)

        # Check snapshot was created
        snapshot_id = reversal.reversal_id.replace("rev-", "snap-")
        snapshot = coordinator.snapshot_manager.get_snapshot(snapshot_id)
        assert snapshot is not None
        assert snapshot.reversal_id == reversal.reversal_id

    def test_execute_reversal_invalid_status(self, tmp_path: Path) -> None:
        """Test that execution fails for invalid status."""
        reversal_dir = tmp_path / "reversals"
        coordinator = ReversalCoordinator(reversal_dir)

        reversal = coordinator.create_reversal(
            batch_id="wb-2025-12-18-0006",
            reversal_type="FULL",
            reason="Test invalid status",
        )

        # Execute once
        coordinator.execute_reversal(reversal.reversal_id)

        # Try to execute again (status is COMPLETED)
        with pytest.raises(ValueError, match="Cannot execute reversal in status"):
            coordinator.execute_reversal(reversal.reversal_id)

    def test_verify_reversal_success(self, tmp_path: Path) -> None:
        """Test verifying a successful reversal."""
        reversal_dir = tmp_path / "reversals"
        coordinator = ReversalCoordinator(reversal_dir)

        reversal = coordinator.create_reversal(
            batch_id="wb-2025-12-18-0007",
            reversal_type="FULL",
            reason="Test verification",
        )

        coordinator.execute_reversal(reversal.reversal_id)

        result = coordinator.verify_reversal(reversal.reversal_id)

        assert result.success is True
        assert "successfully" in result.message.lower()
        assert len(result.failed_actions) == 0

    def test_verify_reversal_not_found(self, tmp_path: Path) -> None:
        """Test verifying non-existent reversal."""
        reversal_dir = tmp_path / "reversals"
        coordinator = ReversalCoordinator(reversal_dir)

        result = coordinator.verify_reversal("rev-nonexistent")

        assert result.success is False
        assert "not found" in result.message.lower()

    def test_verify_reversal_not_completed(self, tmp_path: Path) -> None:
        """Test verifying reversal that hasn't been executed."""
        reversal_dir = tmp_path / "reversals"
        coordinator = ReversalCoordinator(reversal_dir)

        reversal = coordinator.create_reversal(
            batch_id="wb-2025-12-18-0008",
            reversal_type="FULL",
            reason="Test incomplete",
        )

        result = coordinator.verify_reversal(reversal.reversal_id)

        assert result.success is False
        assert "not completed" in result.message.lower()

    def test_get_compensating_actions(self, tmp_path: Path) -> None:
        """Test computing compensating actions."""
        reversal_dir = tmp_path / "reversals"
        coordinator = ReversalCoordinator(reversal_dir)

        actions = coordinator.get_compensating_actions("wb-2025-12-18-0009")

        assert len(actions) > 0
        assert all(isinstance(a, CompensatingAction) for a in actions)

    def test_reversal_moved_to_closed_on_completion(self, tmp_path: Path) -> None:
        """Test that completed reversal is moved to closed directory."""
        reversal_dir = tmp_path / "reversals"
        coordinator = ReversalCoordinator(reversal_dir)

        reversal = coordinator.create_reversal(
            batch_id="wb-2025-12-18-0010",
            reversal_type="FULL",
            reason="Test closure",
        )

        coordinator.execute_reversal(reversal.reversal_id)

        # Should not be in active
        active_path = reversal_dir / "active" / f"{reversal.reversal_id}.json"
        assert not active_path.exists()

        # Should be in closed
        closed_files = list(reversal_dir.glob(f"closed/**/{reversal.reversal_id}.json"))
        assert len(closed_files) == 1


class TestReversalSchemas:
    """Test reversal schema serialization."""

    def test_reversal_batch_roundtrip(self) -> None:
        """Test ReversalBatch serialization and deserialization."""
        from motus.coordination.schemas import ReversalItem

        now = datetime.now(timezone.utc)
        reversal = ReversalBatch(
            schema=REVERSAL_BATCH_SCHEMA,
            reversal_id="rev-2025-12-18-0001",
            reverses_batch_id="wb-2025-12-18-0001",
            reversal_type="FULL",
            status="COMPLETED",
            reason="Test reversal",
            created_at=now,
            created_by="test-agent",
            items_to_reverse=[
                ReversalItem(
                    work_item_id="CR-test-1",
                    original_status="COMPLETED",
                    compensating_action="REVERT_TO_QUEUED",
                    artifacts_to_remove=["foo.py"],
                    status="COMPLETED",
                )
            ],
            compensating_actions_log=[
                CompensatingAction(
                    action_id="ca-001",
                    action_type="FILE_DELETE",
                    target="foo.py",
                    executed_at=now,
                    result="SUCCESS",
                    before_hash="sha256:abc",
                    after_hash="sha256:def",
                )
            ],
            reversal_hash="sha256:ghi",
            original_batch_hash="sha256:jkl",
        )

        # Serialize
        json_data = reversal.to_json()

        # Deserialize
        reversal2 = ReversalBatch.from_json(json_data)

        assert reversal2.reversal_id == reversal.reversal_id
        assert reversal2.status == reversal.status
        assert reversal2.created_by == reversal.created_by
        assert len(reversal2.items_to_reverse) == 1
        assert len(reversal2.compensating_actions_log) == 1

    def test_compensating_action_roundtrip(self) -> None:
        """Test CompensatingAction serialization."""
        now = datetime.now(timezone.utc)
        action = CompensatingAction(
            action_id="ca-001",
            action_type="FILE_RESTORE",
            target="test.py",
            executed_at=now,
            result="SUCCESS",
            before_hash="sha256:abc",
            after_hash="sha256:def",
        )

        json_data = action.to_json()
        action2 = CompensatingAction.from_json(json_data)

        assert action2.action_id == action.action_id
        assert action2.action_type == action.action_type
        assert action2.result == action.result
