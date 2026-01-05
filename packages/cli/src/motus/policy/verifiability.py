# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Evidence bundle verifiability helpers (hashing + signing).

This module intentionally uses only the Python standard library.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from motus.observability.io_capture import record_file_read
from motus.policy.contracts import ArtifactHash

SIGNATURE_PREFIX_HMAC_SHA256 = "hmac-sha256:"
MAX_EVIDENCE_FILES = int(os.environ.get("MC_EVIDENCE_MAX_FILES", "10000"))
MAX_EVIDENCE_DEPTH = int(os.environ.get("MC_EVIDENCE_MAX_DEPTH", "10"))


def _bounded_artifact_paths(root: Path) -> list[Path]:
    root = root.resolve()
    root_depth = len(root.parts)
    paths: list[Path] = []
    for current_root, dirs, files in os.walk(root):
        depth = len(Path(current_root).parts) - root_depth
        if depth >= MAX_EVIDENCE_DEPTH:
            dirs[:] = []
        for name in files:
            paths.append(Path(current_root) / name)
            if len(paths) >= MAX_EVIDENCE_FILES:
                raise ValueError(
                    "Evidence directory exceeds limits. "
                    "Set MC_EVIDENCE_MAX_FILES/MC_EVIDENCE_MAX_DEPTH to override."
                )
    return paths


def sha256_file(path: Path) -> str:
    """Return the SHA-256 hex digest for a file."""
    h = hashlib.sha256()
    bytes_read = 0
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 64), b""):
            h.update(chunk)
            bytes_read += len(chunk)
    record_file_read(path, bytes_read=bytes_read, source="sha256_file")
    return h.hexdigest()


def compute_artifact_hashes(
    evidence_dir: Path, *, exclude_paths: set[str] | None = None
) -> list[ArtifactHash]:
    """Compute SHA-256 hashes for evidence artifacts under `evidence_dir`.

    Hashes are deterministic: artifacts are ordered by their relative POSIX path.
    """
    exclude = exclude_paths or set()
    items: list[ArtifactHash] = []
    evidence_dir_resolved = Path(os.path.realpath(evidence_dir))
    paths = [Path(os.path.realpath(p)) for p in _bounded_artifact_paths(evidence_dir_resolved)]
    for path in sorted(paths, key=lambda p: p.relative_to(evidence_dir_resolved).as_posix()):
        if not path.is_file():
            continue
        rel = path.relative_to(evidence_dir_resolved).as_posix()
        if rel in exclude:
            continue
        items.append(ArtifactHash(path=rel, sha256=sha256_file(path)))
    return items


def _canonical_json_bytes(data: dict) -> bytes:
    """Canonical JSON bytes for hashing.

    This is a deterministic subset compatible with our current manifest contents:
    - UTF-8
    - sorted object keys
    - no insignificant whitespace
    - NaN/Infinity disallowed
    """
    return json.dumps(
        data,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def compute_run_hash(manifest_dict: dict) -> str:
    """Compute the run hash over canonical manifest JSON bytes.

    Excludes self-referential fields: `run_hash` and `signature`.
    """
    material = dict(manifest_dict)
    material.pop("run_hash", None)
    material.pop("signature", None)

    return hashlib.sha256(_canonical_json_bytes(material)).hexdigest()


def sign_run_hash_hmac_sha256(*, run_hash: str, signing_key: str) -> str:
    """Sign `run_hash` using HMAC-SHA256.

    Returns a stable string prefixed with `hmac-sha256:`.
    """
    digest = hmac.new(
        signing_key.encode("utf-8"),
        run_hash.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"{SIGNATURE_PREFIX_HMAC_SHA256}{digest}"


def verify_hmac_sha256_signature(*, run_hash: str, signature: str, signing_key: str) -> bool:
    if not signature.startswith(SIGNATURE_PREFIX_HMAC_SHA256):
        return False
    expected = sign_run_hash_hmac_sha256(run_hash=run_hash, signing_key=signing_key)
    return hmac.compare_digest(expected, signature)


def _parse_iso_datetime(value: str) -> datetime | None:
    raw = value.strip()
    if not raw:
        return None
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return None


@dataclass(frozen=True)
class PrevRunCandidate:
    created_at: datetime
    run_dir: Path
    run_hash: str


def find_prev_run_hash(*, evidence_base_dir: Path, exclude_run_id: str) -> str | None:
    """Find the most recent `run_hash` in the evidence base dir.

    Uses `created_at` from each run's manifest when available; ignores runs without a `run_hash`.
    """
    if not evidence_base_dir.exists():
        return None

    candidates: list[PrevRunCandidate] = []
    for run_dir in evidence_base_dir.iterdir():
        if not run_dir.is_dir():
            continue
        if run_dir.name == exclude_run_id:
            continue

        manifest_path = run_dir / "manifest.json"
        if not manifest_path.exists():
            continue

        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue

        created_at_raw = str(manifest.get("created_at") or "").strip()
        created_at = _parse_iso_datetime(created_at_raw)
        run_hash = str(manifest.get("run_hash") or "").strip()
        if created_at is None or not run_hash:
            continue

        candidates.append(
            PrevRunCandidate(created_at=created_at, run_dir=run_dir, run_hash=run_hash)
        )

    if not candidates:
        return None

    candidates.sort(key=lambda c: (c.created_at, c.run_dir.name))
    return candidates[-1].run_hash
