# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Decision trace + pack match trace helpers for policy runs."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Sequence

from motus.atomic_io import atomic_write_json
from motus.orient.fs_resolver import find_motus_dir
from motus.policy.contracts import VaultPolicyBundle
from motus.policy.globs import glob_match

TRACE_VERSION = "1.0.0"
TRACE_DATE_FORMAT = "%Y-%m-%d"


@dataclass(frozen=True)
class TracePaths:
    trace_base_dir: Path
    trace_day_dir: Path
    decision_trace_paths: list[Path]
    pack_match_trace_paths: list[Path]
    handoff_paths: list[Path]
    last_run_id_path: Path


def _parse_iso_date(value: str | None) -> str:
    if not value:
        return datetime.now(timezone.utc).strftime(TRACE_DATE_FORMAT)
    try:
        return datetime.fromisoformat(value).strftime(TRACE_DATE_FORMAT)
    except ValueError:
        return datetime.now(timezone.utc).strftime(TRACE_DATE_FORMAT)


def _trace_base_dir(repo_dir: Path) -> Path:
    motus_dir = find_motus_dir(repo_dir)
    if motus_dir is not None:
        return motus_dir
    return repo_dir / ".mc"


def ensure_trace_paths(
    *,
    repo_dir: Path,
    evidence_dir: Path,
    run_id: str,
    created_at: str | None,
) -> TracePaths:
    base_dir = _trace_base_dir(repo_dir)
    base_dir.mkdir(parents=True, exist_ok=True)
    trace_day_dir = base_dir / "traces" / _parse_iso_date(created_at)
    trace_day_dir.mkdir(parents=True, exist_ok=True)

    decision_trace_paths = [
        evidence_dir / "decision_trace.jsonl",
        trace_day_dir / f"decision_trace_{run_id}.jsonl",
    ]
    pack_match_trace_paths = [
        evidence_dir / "pack_match_trace.json",
        trace_day_dir / f"pack_match_trace_{run_id}.json",
    ]
    handoff_paths = [
        evidence_dir / "handoff.json",
        trace_day_dir / f"handoff_{run_id}.json",
    ]
    last_run_id_path = base_dir / "last-run-id"
    return TracePaths(
        trace_base_dir=base_dir,
        trace_day_dir=trace_day_dir,
        decision_trace_paths=decision_trace_paths,
        pack_match_trace_paths=pack_match_trace_paths,
        handoff_paths=handoff_paths,
        last_run_id_path=last_run_id_path,
    )


def ensure_plan_trace_paths(
    *,
    repo_dir: Path,
    plan_id: str,
    created_at: str | None,
) -> list[Path]:
    base_dir = _trace_base_dir(repo_dir)
    base_dir.mkdir(parents=True, exist_ok=True)
    trace_day_dir = base_dir / "traces" / _parse_iso_date(created_at)
    trace_day_dir.mkdir(parents=True, exist_ok=True)
    return [trace_day_dir / f"pack_match_trace_{plan_id}.json"]


def _hash_bytes(chunks: Iterable[bytes]) -> str:
    digest = hashlib.sha256()
    for chunk in chunks:
        digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def hash_json(data: object) -> str:
    payload = json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return _hash_bytes([payload])


def hash_files(paths: Sequence[Path], *, extra: str | None = None) -> str:
    digest = hashlib.sha256()
    for path in paths:
        try:
            digest.update(path.read_bytes())
        except OSError:
            digest.update(f"missing:{path}".encode("utf-8"))
    if extra:
        digest.update(extra.encode("utf-8"))
    return f"sha256:{digest.hexdigest()}"


class DecisionTraceWriter:
    def __init__(self, trace_paths: Sequence[Path]):
        self._trace_paths = list(trace_paths)
        self._prev_hash: str | None = None
        self.events: list[dict] = []
        for path in self._trace_paths:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.touch(exist_ok=True)

    def append_event(self, event: dict) -> dict:
        chained = dict(event)
        if self._prev_hash:
            chained["prev_hash"] = self._prev_hash
        payload = json.dumps(chained, sort_keys=True, separators=(",", ":")).encode("utf-8")
        event_hash = f"sha256:{hashlib.sha256(payload).hexdigest()}"
        chained["event_hash"] = event_hash
        self._prev_hash = event_hash
        self.events.append(chained)
        line = json.dumps(chained, sort_keys=True)
        for path in self._trace_paths:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")
        return chained


def write_pack_match_trace(
    *,
    changed_files: Sequence[str],
    policy: VaultPolicyBundle,
    created_at: str | None,
    output_paths: Sequence[Path],
    run_id: str | None = None,
    plan_id: str | None = None,
) -> dict:
    entries: list[dict] = []
    for file_path in changed_files:
        matched_packs: list[str] = []
        matched_scopes: list[str] = []
        for pack in policy.pack_registry.packs:
            matched = [scope for scope in pack.scopes if glob_match(scope, file_path)]
            if matched:
                matched_packs.append(pack.id)
                matched_scopes.extend(matched)
        match_reason = "scopes:" + ", ".join(matched_scopes) if matched_scopes else "no_match"
        entries.append(
            {
                "file": file_path,
                "matched_packs": matched_packs,
                "matched_scopes": matched_scopes,
                "match_reason": match_reason,
            }
        )

    payload: dict = {
        "version": TRACE_VERSION,
        "created_at": created_at or datetime.now(timezone.utc).isoformat(),
        "entries": entries,
    }
    if run_id:
        payload["run_id"] = run_id
    if plan_id:
        payload["plan_id"] = plan_id

    for path in output_paths:
        path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_json(path, payload, sort_keys=True)

    return payload


def write_last_run_id(path: Path, run_id: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(run_id + "\n", encoding="utf-8")


def write_handoff_artifact(
    *,
    output_paths: Sequence[Path],
    run_id: str,
    summary: str,
    first_failed_gate: str | None,
    reason_codes: Sequence[str],
    trace_path: str,
    manifest_path: str,
    summary_path: str,
) -> None:
    payload = {
        "run_id": run_id,
        "summary": summary,
        "first_failed_gate": first_failed_gate,
        "reason_codes": list(reason_codes),
        "trace_path": trace_path,
        "manifest_path": manifest_path,
        "summary_path": summary_path,
    }
    for path in output_paths:
        path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_json(path, payload, sort_keys=True)
