from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from motus.policy.cleanup import prune_evidence_bundles


def _write_bundle(run_dir: Path, *, created_at: datetime, payload_bytes: int = 0) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "logs").mkdir(parents=True, exist_ok=True)

    manifest = {"created_at": created_at.isoformat(), "run_id": run_dir.name, "version": "1.0.0"}
    (run_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (run_dir / "summary.md").write_text("# summary\n", encoding="utf-8")
    if payload_bytes:
        (run_dir / "logs" / "payload.bin").write_bytes(b"x" * payload_bytes)


def test_policy_prune_keep_n(tmp_path: Path) -> None:
    base = tmp_path / "evidence"
    t0 = datetime(2025, 1, 1, tzinfo=timezone.utc)

    _write_bundle(base / "run-a", created_at=t0, payload_bytes=10)
    _write_bundle(base / "run-b", created_at=t0 + timedelta(days=1), payload_bytes=20)
    _write_bundle(base / "run-c", created_at=t0 + timedelta(days=2), payload_bytes=30)

    result = prune_evidence_bundles(evidence_base_dir=base, keep=2, older_than_days=None)

    assert result.bundles_found == 3
    assert result.bundles_deleted == 1
    assert (base / "run-a").exists() is False
    assert (base / "run-b").exists()
    assert (base / "run-c").exists()


def test_policy_prune_older_than_days(tmp_path: Path) -> None:
    base = tmp_path / "evidence"
    now = datetime(2025, 1, 20, tzinfo=timezone.utc)

    _write_bundle(base / "old-1", created_at=now - timedelta(days=30), payload_bytes=10)
    _write_bundle(base / "old-2", created_at=now - timedelta(days=8), payload_bytes=20)
    _write_bundle(base / "new-1", created_at=now - timedelta(days=2), payload_bytes=30)

    result = prune_evidence_bundles(evidence_base_dir=base, keep=10, older_than_days=7, now=now)

    assert result.bundles_found == 3
    assert result.bundles_deleted == 2
    assert (base / "old-1").exists() is False
    assert (base / "old-2").exists() is False
    assert (base / "new-1").exists()


def test_policy_prune_dry_run_does_not_delete(tmp_path: Path) -> None:
    base = tmp_path / "evidence"
    t0 = datetime(2025, 1, 1, tzinfo=timezone.utc)

    _write_bundle(base / "run-1", created_at=t0, payload_bytes=10)
    _write_bundle(base / "run-2", created_at=t0 + timedelta(days=1), payload_bytes=20)
    _write_bundle(base / "run-3", created_at=t0 + timedelta(days=2), payload_bytes=30)

    result = prune_evidence_bundles(evidence_base_dir=base, keep=1, dry_run=True)

    assert result.bundles_deleted == 2
    assert (base / "run-1").exists()
    assert (base / "run-2").exists()
    assert (base / "run-3").exists()
