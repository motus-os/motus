# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

from motus.atomic_io import atomic_write_text
from motus.coordination.namespace_acl import NamespaceACL
from motus.coordination.schemas import ClaimedResource, ClaimRecord
from motus.file_lock import FileLockError, file_lock


class ClaimRegistryError(Exception):
    pass


_LOCK_TIMEOUT_SECONDS = 5.0


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _posix(path: str) -> PurePosixPath:
    return PurePosixPath(path.replace("\\", "/"))


def _norm_namespace(namespace: str | None) -> str:
    return (namespace or "default").strip() or "default"


def _resources_overlap(a: ClaimedResource, b: ClaimedResource) -> bool:
    a_path = _posix(a.path)
    b_path = _posix(b.path)

    a_type = a.type.lower()
    b_type = b.type.lower()

    if a_type == "file" and b_type == "file":
        return a_path == b_path

    if a_type == "directory" and b_type == "directory":
        return a_path == b_path or str(a_path).startswith(f"{b_path}/") or str(b_path).startswith(f"{a_path}/")

    if a_type == "directory" and b_type == "file":
        return b_path == a_path or str(b_path).startswith(f"{a_path}/")
    if a_type == "file" and b_type == "directory":
        return a_path == b_path or str(a_path).startswith(f"{b_path}/")

    return a.type == b.type and a_path == b_path


class _ClaimStorage:
    def __init__(self, root_dir: str | Path, *, namespace_acl: NamespaceACL | None = None) -> None:
        self._root = Path(root_dir)
        self._sequence_path = self._root / "SEQUENCE"
        self._acl = namespace_acl

    def _claim_path(self, claim_id: str) -> Path:
        return self._root / f"{claim_id}.json"

    def _list_claim_files(self) -> list[Path]:
        if not self._root.exists():
            return []
        return sorted(p for p in self._root.glob("cl-*.json") if p.is_file())

    def _load_claim(self, path: Path) -> ClaimRecord:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:  # noqa: BLE001
            raise ClaimRegistryError(f"failed to read claim file: {path}") from e
        try:
            return ClaimRecord.from_json(payload)
        except Exception as e:  # noqa: BLE001
            raise ClaimRegistryError(f"invalid claim payload: {path}") from e

    def _is_expired(self, claim: ClaimRecord, *, now: datetime) -> bool:
        return now >= claim.expires_at

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
            raise ClaimRegistryError(
                f"failed to lock claim sequence file: {self._sequence_path}"
            ) from exc
