# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Evidence bundle cleanup utilities for `motus policy`."""

from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from motus.exceptions import ConfigError

MAX_EVIDENCE_FILES = int(os.environ.get("MC_EVIDENCE_MAX_FILES", "10000"))
MAX_EVIDENCE_DEPTH = int(os.environ.get("MC_EVIDENCE_MAX_DEPTH", "10"))


def _bounded_file_iter(root: Path) -> list[Path]:
    root = root.resolve()
    root_depth = len(root.parts)
    files: list[Path] = []
    for current_root, dirs, filenames in os.walk(root):
        depth = len(Path(current_root).parts) - root_depth
        if depth >= MAX_EVIDENCE_DEPTH:
            dirs[:] = []
        for name in filenames:
            files.append(Path(current_root) / name)
            if len(files) >= MAX_EVIDENCE_FILES:
                raise ConfigError(
                    "Evidence bundle exceeds limits",
                    details=(
                        "Increase MC_EVIDENCE_MAX_FILES/MC_EVIDENCE_MAX_DEPTH "
                        "or prune the bundle."
                    ),
                )
    return files


def _parse_iso_datetime(value: str) -> datetime | None:
    raw = value.strip()
    if not raw:
        return None
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _dir_total_bytes(path: Path) -> int:
    total = 0
    for item in _bounded_file_iter(path):
        try:
            total += item.stat().st_size
        except OSError:
            continue
    return total


@dataclass(frozen=True)
class EvidenceBundle:
    run_id: str
    run_dir: Path
    created_at: datetime
    total_bytes: int


@dataclass(frozen=True)
class PruneResult:
    evidence_base_dir: Path
    bundles_found: int
    bundles_kept: int
    bundles_deleted: int
    reclaimed_bytes: int
    deleted_run_ids: tuple[str, ...]


def list_evidence_bundles(evidence_base_dir: Path) -> list[EvidenceBundle]:
    if not evidence_base_dir.exists():
        return []

    bundles: list[EvidenceBundle] = []
    for run_dir in evidence_base_dir.iterdir():
        if not run_dir.is_dir():
            continue

        created_at = None
        manifest_path = run_dir / "manifest.json"
        if manifest_path.exists():
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                created_at_raw = str(manifest.get("created_at") or "")
                created_at = _parse_iso_datetime(created_at_raw)
            except (OSError, json.JSONDecodeError):
                created_at = None

        if created_at is None:
            try:
                created_at = datetime.fromtimestamp(run_dir.stat().st_mtime, tz=timezone.utc)
            except OSError:
                created_at = datetime.fromtimestamp(0, tz=timezone.utc)

        bundles.append(
            EvidenceBundle(
                run_id=run_dir.name,
                run_dir=run_dir,
                created_at=created_at,
                total_bytes=_dir_total_bytes(run_dir),
            )
        )

    bundles.sort(key=lambda b: (b.created_at, b.run_id))
    return bundles


def prune_evidence_bundles(
    *,
    evidence_base_dir: Path,
    keep: int = 10,
    older_than_days: int | None = None,
    dry_run: bool = False,
    now: datetime | None = None,
) -> PruneResult:
    if keep < 0:
        raise ConfigError("Invalid --keep", details="Expected an integer >= 0")
    if older_than_days is not None and older_than_days < 0:
        raise ConfigError("Invalid --older-than", details="Expected an integer >= 0")

    bundles = list_evidence_bundles(evidence_base_dir)
    if not bundles:
        return PruneResult(
            evidence_base_dir=evidence_base_dir,
            bundles_found=0,
            bundles_kept=0,
            bundles_deleted=0,
            reclaimed_bytes=0,
            deleted_run_ids=(),
        )

    effective_now = now or datetime.now(timezone.utc)

    delete_ids: set[str] = set()
    if older_than_days is not None:
        cutoff = effective_now - timedelta(days=older_than_days)
        delete_ids |= {b.run_id for b in bundles if b.created_at < cutoff}

    survivors = [b for b in bundles if b.run_id not in delete_ids]
    if keep == 0:
        delete_ids |= {b.run_id for b in survivors}
    elif keep > 0 and len(survivors) > keep:
        keep_set = {b.run_id for b in survivors[-keep:]}
        delete_ids |= {b.run_id for b in survivors if b.run_id not in keep_set}

    delete_candidates = [b for b in bundles if b.run_id in delete_ids]
    reclaimed = sum(b.total_bytes for b in delete_candidates)
    deleted_ids: list[str] = [b.run_id for b in delete_candidates]

    if not dry_run:
        for bundle in delete_candidates:
            try:
                shutil.rmtree(bundle.run_dir, ignore_errors=False)
            except OSError as e:
                raise ConfigError(
                    "Failed to prune evidence bundle",
                    details=f"run_id={bundle.run_id} path={bundle.run_dir}: {e}",
                ) from e
    kept = [b for b in bundles if b.run_id not in delete_ids]

    return PruneResult(
        evidence_base_dir=evidence_base_dir,
        bundles_found=len(bundles),
        bundles_kept=len(kept),
        bundles_deleted=len(deleted_ids),
        reclaimed_bytes=reclaimed,
        deleted_run_ids=tuple(deleted_ids),
    )
