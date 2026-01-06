# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

from __future__ import annotations

import hashlib
import json
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from motus.atomic_io import atomic_write_json
from motus.core.database_connection import get_db_manager
from motus.orient.fs_resolver import find_motus_dir

from .schemas import (
    SCRATCH_ENTRY_SCHEMA,
    SCRATCH_INDEX_SCHEMA,
    ScratchEntry,
    ScratchIndex,
    ScratchIndexEntry,
    ScratchRoadmapLink,
)


class ScratchStoreError(Exception):
    pass


class ScratchEntryNotFound(ScratchStoreError):
    pass


class ScratchPromotionError(ScratchStoreError):
    pass


@dataclass(frozen=True, slots=True)
class ScratchPromotionResult:
    entry_id: str
    roadmap_id: str
    decision_id: str
    evidence_id: str


def _utc_now_iso_z() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _utc_today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _safe_entry_filename(entry_id: str) -> str:
    if "/" in entry_id or "\\" in entry_id:
        raise ValueError(f"invalid entry_id for filename: {entry_id!r}")
    return f"{entry_id}.json"


def _resolve_agent_id() -> str:
    for env_var in ("MC_AGENT_ID", "MOTUS_AGENT_ID"):
        value = os.environ.get(env_var, "").strip()
        if value:
            return value
    return "user"


def _generate_id(prefix: str) -> str:
    from motus.core.sqlite_udfs import mc_id

    seed = uuid.uuid4().hex
    return mc_id(prefix, seed) or f"{prefix}-{seed[:12]}"


def _next_entry_id(root: Path) -> str:
    prefix = f"SCR-{_utc_today()}"
    max_suffix = 0
    if root.exists():
        for path in root.glob(f"{prefix}-*.json"):
            if path.name == "INDEX.json":
                continue
            suffix = path.stem.rsplit("-", 1)[-1]
            if suffix.isdigit():
                max_suffix = max(max_suffix, int(suffix))
    return f"{prefix}-{max_suffix + 1:03d}"


def _next_roadmap_id(conn, *, prefix: str) -> str:
    like = f"{prefix}-%"
    row = conn.execute(
        "SELECT id FROM roadmap_items WHERE id LIKE ? ORDER BY id DESC LIMIT 1",
        (like,),
    ).fetchone()
    if row and row[0]:
        last = str(row[0])
        try:
            suffix = int(last.rsplit("-", 1)[-1])
        except ValueError:
            suffix = 0
    else:
        suffix = 0
    return f"{prefix}-{suffix + 1:03d}"


def _normalize_tags(tags: list[str] | None) -> list[str]:
    if not tags:
        return []
    normalized = [t.strip() for t in tags if t and t.strip()]
    return sorted(set(normalized))


def _entry_artifacts(entry: ScratchEntry, *, path: Path) -> dict[str, Any]:
    return {
        "scratch_entry_id": entry.entry_id,
        "scratch_path": str(path),
        "title": entry.title,
        "status": entry.status,
        "created_at": entry.created_at,
    }


class ScratchStore:
    def __init__(self, root: Path) -> None:
        self._root = root
        self._index_path = root / "INDEX.json"

    @property
    def root(self) -> Path:
        return self._root

    @classmethod
    def from_cwd(cls, cwd: Path | None = None) -> "ScratchStore":
        motus_dir = find_motus_dir(cwd or Path.cwd())
        if motus_dir is None:
            raise ScratchStoreError("Not in a Motus workspace (missing .motus)")
        return cls(motus_dir / "scratch")

    def _ensure_root(self) -> None:
        self._root.mkdir(parents=True, exist_ok=True)

    def _entry_path(self, entry_id: str) -> Path:
        return self._root / _safe_entry_filename(entry_id)

    def create_entry(
        self,
        *,
        title: str,
        body: str | None = None,
        tags: list[str] | None = None,
        created_by: str | None = None,
    ) -> ScratchEntry:
        title_clean = (title or "").strip()
        if not title_clean:
            raise ScratchStoreError("title is required")
        body_clean = (body or "").strip()

        self._ensure_root()
        entry_id = _next_entry_id(self._root)
        now = _utc_now_iso_z()
        entry = ScratchEntry(
            schema=SCRATCH_ENTRY_SCHEMA,
            entry_id=entry_id,
            title=title_clean,
            body=body_clean,
            tags=_normalize_tags(tags),
            status="open",
            created_at=now,
            updated_at=now,
            created_by=created_by or _resolve_agent_id(),
            roadmap=None,
        )
        atomic_write_json(self._entry_path(entry_id), entry.to_json())
        self.rebuild_index()
        return entry

    def load_entry(self, entry_id: str) -> ScratchEntry:
        path = self._entry_path(entry_id)
        if not path.exists():
            raise ScratchEntryNotFound(f"Scratch entry not found: {entry_id}")
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ScratchStoreError(f"Scratch entry invalid: {entry_id}")
        return ScratchEntry.from_json(raw)

    def save_entry(self, entry: ScratchEntry) -> None:
        self._ensure_root()
        atomic_write_json(self._entry_path(entry.entry_id), entry.to_json())

    def rebuild_index(self) -> ScratchIndex:
        self._ensure_root()
        entries: list[ScratchIndexEntry] = []
        for path in sorted(self._root.glob("*.json")):
            if path.name == "INDEX.json" or path.name.startswith("."):
                continue
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                if not isinstance(raw, dict):
                    continue
                entry = ScratchEntry.from_json(raw)
                entries.append(ScratchIndexEntry.from_entry(entry))
            except Exception:
                continue

        entries.sort(key=lambda e: (e.created_at, e.entry_id))
        index = ScratchIndex(
            schema=SCRATCH_INDEX_SCHEMA,
            generated_at=_utc_now_iso_z(),
            entries=entries,
        )
        atomic_write_json(self._index_path, index.to_json())
        return index

    def load_index(self, *, rebuild_on_error: bool = True) -> ScratchIndex:
        if not self._index_path.exists():
            return self.rebuild_index()
        try:
            raw = json.loads(self._index_path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raise ValueError("Scratch index invalid")
            return ScratchIndex.from_json(raw)
        except Exception:
            if rebuild_on_error:
                return self.rebuild_index()
            raise

    def list_entries(self) -> list[ScratchIndexEntry]:
        index = self.load_index()
        return list(index.entries)

    def promote_to_roadmap(
        self,
        entry_id: str,
        *,
        phase_key: str,
        item_type: str = "work",
        title: str | None = None,
        description: str | None = None,
        promoted_by: str | None = None,
    ) -> ScratchPromotionResult:
        phase_key_clean = (phase_key or "").strip()
        if not phase_key_clean:
            raise ScratchPromotionError("phase_key is required")
        item_type_clean = (item_type or "").strip() or "work"

        entry = self.load_entry(entry_id)
        if entry.roadmap is not None or entry.status == "promoted":
            raise ScratchPromotionError(f"Entry already promoted: {entry_id}")

        title_value = (title or "").strip() or entry.title
        description_value = (description or "").strip() or entry.body
        actor = promoted_by or _resolve_agent_id()
        now = _utc_now_iso_z()

        db = get_db_manager()
        with db.transaction() as conn:
            roadmap_id = _next_roadmap_id(conn, prefix=f"RI-SCR-{_utc_today()}")
            conn.execute(
                """
                INSERT INTO roadmap_items (
                    id, phase_key, title, description, status_key, owner, item_type, created_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    roadmap_id,
                    phase_key_clean,
                    title_value,
                    description_value,
                    "pending",
                    actor,
                    item_type_clean,
                    actor,
                ),
            )

            decision_id = _generate_id("decision")
            decision_summary = f"Promoted scratch {entry_id} to roadmap {roadmap_id}"
            conn.execute(
                """
                INSERT INTO decisions (
                    id, work_id, attempt_id, lease_id, decision_type, decision_summary,
                    rationale, alternatives_considered, constraints, decided_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    decision_id,
                    roadmap_id,
                    None,
                    f"scratch:{entry_id}",
                    "plan_committed",
                    decision_summary,
                    entry.body or None,
                    json.dumps([]),
                    json.dumps([]),
                    actor,
                ),
            )

            evidence_id = _generate_id("evidence")
            artifacts = _entry_artifacts(entry, path=self._entry_path(entry_id))
            artifacts_json = json.dumps(artifacts, sort_keys=True, separators=(",", ":"))
            sha256 = hashlib.sha256(artifacts_json.encode("utf-8")).hexdigest()
            conn.execute(
                """
                INSERT INTO evidence (
                    id, work_id, attempt_id, lease_id, evidence_type, uri, sha256,
                    artifacts, test_results, diff_summary, log_excerpt, created_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    evidence_id,
                    roadmap_id,
                    None,
                    f"scratch:{entry_id}",
                    "document",
                    f"scratch:{entry_id}",
                    sha256,
                    artifacts_json,
                    None,
                    None,
                    None,
                    actor,
                ),
            )

        updated_entry = ScratchEntry(
            schema=entry.schema,
            entry_id=entry.entry_id,
            title=entry.title,
            body=entry.body,
            tags=entry.tags,
            status="promoted",
            created_at=entry.created_at,
            updated_at=now,
            created_by=entry.created_by,
            roadmap=ScratchRoadmapLink(
                item_id=roadmap_id,
                phase_key=phase_key_clean,
                item_type=item_type_clean,
                promoted_at=now,
                promoted_by=actor,
            ),
        )
        self.save_entry(updated_entry)
        self.rebuild_index()

        return ScratchPromotionResult(
            entry_id=entry_id,
            roadmap_id=roadmap_id,
            decision_id=decision_id,
            evidence_id=evidence_id,
        )


__all__ = [
    "ScratchStore",
    "ScratchEntryNotFound",
    "ScratchPromotionError",
    "ScratchPromotionResult",
]
