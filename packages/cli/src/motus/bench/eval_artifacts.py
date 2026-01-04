# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Benchmark evaluation artifacts (run manifests + hash-chained events).

These utilities support Phase 0.1.4 benchmarks where results must be
recomputable from raw artifacts (no-theater reporting).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from motus.atomic_io import atomic_write_json
from motus.file_lock import FileLockError, file_lock

EVENT_SCHEMA_VERSION = "0.1.0"
RUN_MANIFEST_SCHEMA_VERSION = "0.1.0"
_EMPTY_SHA256 = "0" * 64


def _canonical_json_bytes(data: dict) -> bytes:
    return json.dumps(
        data,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def sha256_hex_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_hex_text(text: str) -> str:
    return sha256_hex_bytes(text.encode("utf-8"))


def sha256_hex_file(path: Path) -> str:
    h = hashlib.sha256()
    try:
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(1024 * 64), b""):
                h.update(chunk)
    except OSError as e:
        raise RuntimeError(f"failed to read file for sha256: {path}: {e}") from e
    return h.hexdigest()


def sha256_ref(hex_digest: str) -> str:
    return f"sha256:{hex_digest}"


def write_json(path: Path, payload: dict) -> None:
    atomic_write_json(path, payload, sort_keys=True)


@dataclass(frozen=True)
class EventChainResult:
    ok: bool
    head_hash: str
    error: str | None = None


class EventChainWriter:
    def __init__(self, path: Path, *, start_prev_hash: str | None = None) -> None:
        self._path = path
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            raise RuntimeError(f"failed to create event chain dir: {self._path.parent}: {e}") from e
        self._prev_hash = start_prev_hash or _EMPTY_SHA256

    @property
    def head_hash(self) -> str:
        return self._prev_hash

    def append(self, *, ts: str, event_type: str, payload: dict | None = None) -> dict:
        event: dict = {
            "schema_version": EVENT_SCHEMA_VERSION,
            "ts": ts,
            "type": event_type,
        }
        if payload is not None:
            event["payload"] = payload

        canonical_event = _canonical_json_bytes(event)
        event_hash = sha256_hex_bytes(self._prev_hash.encode("utf-8") + canonical_event)

        record = dict(event)
        record["prev_hash"] = self._prev_hash
        record["event_hash"] = event_hash

        try:
            with file_lock(self._path, exclusive=True):
                with self._path.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")
                    f.flush()
                    try:
                        import os

                        os.fsync(f.fileno())
                    except OSError:
                        pass
        except FileLockError as e:
            raise RuntimeError(f"failed to acquire event chain lock: {self._path}: {e}") from e
        except OSError as e:
            raise RuntimeError(f"failed to append event record: {self._path}: {e}") from e

        self._prev_hash = event_hash
        return record


def verify_event_chain(path: Path) -> EventChainResult:
    if not path.exists():
        return EventChainResult(ok=False, head_hash="", error="events file missing")

    prev_hash = _EMPTY_SHA256
    head = prev_hash
    try:
        with file_lock(path, exclusive=False):
            lines = path.read_text(encoding="utf-8").splitlines()
    except FileLockError as e:
        return EventChainResult(
            ok=False,
            head_hash="",
            error=f"failed to acquire event chain lock: {path}: {e}",
        )
    except OSError as e:
        return EventChainResult(ok=False, head_hash="", error=f"failed to read events: {e}")

    for idx, raw in enumerate(lines, start=1):
        raw = raw.strip()
        if not raw:
            continue
        try:
            record = json.loads(raw)
        except json.JSONDecodeError as e:
            return EventChainResult(
                ok=False, head_hash=head, error=f"line {idx}: invalid json: {e}"
            )
        if not isinstance(record, dict):
            return EventChainResult(ok=False, head_hash=head, error=f"line {idx}: not an object")

        if record.get("prev_hash") != prev_hash:
            return EventChainResult(
                ok=False,
                head_hash=head,
                error=f"line {idx}: prev_hash mismatch (expected {prev_hash}, got {record.get('prev_hash')})",
            )

        event_hash = record.get("event_hash")
        if not isinstance(event_hash, str) or not event_hash:
            return EventChainResult(
                ok=False, head_hash=head, error=f"line {idx}: missing event_hash"
            )

        event = dict(record)
        event.pop("event_hash", None)
        event.pop("prev_hash", None)
        canonical_event = _canonical_json_bytes(event)
        expected = sha256_hex_bytes(prev_hash.encode("utf-8") + canonical_event)
        if expected != event_hash:
            return EventChainResult(
                ok=False,
                head_hash=head,
                error=f"line {idx}: event_hash mismatch (expected {expected}, got {event_hash})",
            )

        prev_hash = event_hash
        head = event_hash

    return EventChainResult(ok=True, head_hash=head)
