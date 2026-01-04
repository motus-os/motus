# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Pre-reversal snapshot capture for safe rollbacks."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from .schemas import SNAPSHOT_SCHEMA, FileState, Snapshot


class SnapshotManager:
    """Captures file states before reversal execution."""

    def __init__(self, snapshot_dir: str | Path) -> None:
        self.snapshot_dir = Path(snapshot_dir)
        self.snapshot_dir.mkdir(parents=True, exist_ok=True)

    def capture_snapshot(self, reversal_id: str, file_paths: list[str]) -> Snapshot:
        """
        Capture current state of files before reversal.

        Args:
            reversal_id: ID of the reversal this snapshot is for
            file_paths: List of file paths to snapshot

        Returns:
            Snapshot object with current file states
        """
        snapshot_id = self._generate_snapshot_id(reversal_id)
        file_states = []

        for file_path in file_paths:
            path_obj = Path(file_path)
            if path_obj.exists():
                file_hash = self._compute_file_hash(path_obj)
                file_states.append(FileState(path=file_path, hash=file_hash, exists=True))
            else:
                file_states.append(FileState(path=file_path, hash="", exists=False))

        snapshot = Snapshot(
            schema=SNAPSHOT_SCHEMA,
            snapshot_id=snapshot_id,
            reversal_id=reversal_id,
            captured_at=datetime.now(timezone.utc),
            file_states=file_states,
        )

        self._save_snapshot(snapshot)
        return snapshot

    def get_snapshot(self, snapshot_id: str) -> Snapshot | None:
        """Load a snapshot by ID."""
        snapshot_path = self.snapshot_dir / f"{snapshot_id}.json"
        if not snapshot_path.exists():
            return None

        with open(snapshot_path) as f:
            data = json.load(f)
        return Snapshot.from_json(data)

    def _generate_snapshot_id(self, reversal_id: str) -> str:
        """Generate snapshot ID from reversal ID."""
        # Extract date portion from reversal_id (e.g., rev-2025-12-18-0001 -> snap-2025-12-18-0001)
        return reversal_id.replace("rev-", "snap-")

    def _compute_file_hash(self, file_path: Path) -> str:
        """Compute SHA256 hash of file contents."""
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            while chunk := f.read(8192):
                sha256.update(chunk)
        return f"sha256:{sha256.hexdigest()}"

    def _save_snapshot(self, snapshot: Snapshot) -> None:
        """Save snapshot to disk."""
        snapshot_path = self.snapshot_dir / f"{snapshot.snapshot_id}.json"
        with open(snapshot_path, "w") as f:
            json.dump(snapshot.to_json(), f, indent=2)
