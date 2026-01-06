# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

SCRATCH_ENTRY_SCHEMA = "motus.scratch.entry.v1"
SCRATCH_INDEX_SCHEMA = "motus.scratch.index.v1"

_ALLOWED_STATUSES = {"open", "promoted"}


def _require_str(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Invalid {field} (expected non-empty string)")
    return value


def _require_list_str(value: Any, *, field: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise ValueError(f"Invalid {field} (expected list[str])")
    return list(value)


@dataclass(frozen=True, slots=True)
class ScratchRoadmapLink:
    item_id: str
    phase_key: str
    item_type: str
    promoted_at: str
    promoted_by: str

    def to_json(self) -> dict[str, Any]:
        return {
            "item_id": self.item_id,
            "phase_key": self.phase_key,
            "item_type": self.item_type,
            "promoted_at": self.promoted_at,
            "promoted_by": self.promoted_by,
        }

    @staticmethod
    def from_json(payload: dict[str, Any]) -> "ScratchRoadmapLink":
        return ScratchRoadmapLink(
            item_id=_require_str(payload.get("item_id"), field="roadmap.item_id"),
            phase_key=_require_str(payload.get("phase_key"), field="roadmap.phase_key"),
            item_type=_require_str(payload.get("item_type"), field="roadmap.item_type"),
            promoted_at=_require_str(payload.get("promoted_at"), field="roadmap.promoted_at"),
            promoted_by=_require_str(payload.get("promoted_by"), field="roadmap.promoted_by"),
        )


@dataclass(frozen=True, slots=True)
class ScratchEntry:
    schema: str
    entry_id: str
    title: str
    body: str
    tags: list[str]
    status: str
    created_at: str
    updated_at: str
    created_by: str | None = None
    roadmap: ScratchRoadmapLink | None = None

    def to_json(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schema": self.schema,
            "entry_id": self.entry_id,
            "title": self.title,
            "body": self.body,
            "tags": list(self.tags),
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "created_by": self.created_by,
        }
        if self.roadmap is not None:
            payload["roadmap"] = self.roadmap.to_json()
        return payload

    @staticmethod
    def from_json(payload: dict[str, Any]) -> "ScratchEntry":
        schema = _require_str(payload.get("schema"), field="schema")
        if schema != SCRATCH_ENTRY_SCHEMA:
            raise ValueError(f"Unsupported scratch schema: {schema}")
        entry_id = _require_str(payload.get("entry_id"), field="entry_id")
        title = _require_str(payload.get("title"), field="title")
        body = payload.get("body")
        if body is None:
            body = ""
        if not isinstance(body, str):
            raise ValueError("Invalid body (expected string)")
        tags = _require_list_str(payload.get("tags"), field="tags")
        status = _require_str(payload.get("status"), field="status")
        if status not in _ALLOWED_STATUSES:
            raise ValueError(f"Invalid status: {status}")
        created_at = _require_str(payload.get("created_at"), field="created_at")
        updated_at = _require_str(payload.get("updated_at"), field="updated_at")
        created_by = payload.get("created_by")
        if created_by is not None and not isinstance(created_by, str):
            raise ValueError("Invalid created_by (expected string)")
        roadmap_payload = payload.get("roadmap")
        roadmap = None
        if roadmap_payload is not None:
            if not isinstance(roadmap_payload, dict):
                raise ValueError("Invalid roadmap (expected mapping)")
            roadmap = ScratchRoadmapLink.from_json(roadmap_payload)
        return ScratchEntry(
            schema=schema,
            entry_id=entry_id,
            title=title,
            body=body,
            tags=tags,
            status=status,
            created_at=created_at,
            updated_at=updated_at,
            created_by=created_by,
            roadmap=roadmap,
        )


@dataclass(frozen=True, slots=True)
class ScratchIndexEntry:
    entry_id: str
    title: str
    status: str
    created_at: str
    updated_at: str
    roadmap_item_id: str | None = None

    def to_json(self) -> dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "title": self.title,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "roadmap_item_id": self.roadmap_item_id,
        }

    @staticmethod
    def from_entry(entry: ScratchEntry) -> "ScratchIndexEntry":
        roadmap_item_id = entry.roadmap.item_id if entry.roadmap else None
        return ScratchIndexEntry(
            entry_id=entry.entry_id,
            title=entry.title,
            status=entry.status,
            created_at=entry.created_at,
            updated_at=entry.updated_at,
            roadmap_item_id=roadmap_item_id,
        )


@dataclass(frozen=True, slots=True)
class ScratchIndex:
    schema: str
    generated_at: str
    entries: list[ScratchIndexEntry]

    def to_json(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "generated_at": self.generated_at,
            "entries": [entry.to_json() for entry in self.entries],
        }

    @staticmethod
    def from_json(payload: dict[str, Any]) -> "ScratchIndex":
        schema = _require_str(payload.get("schema"), field="schema")
        if schema != SCRATCH_INDEX_SCHEMA:
            raise ValueError(f"Unsupported scratch index schema: {schema}")
        generated_at = _require_str(payload.get("generated_at"), field="generated_at")
        entries_raw = payload.get("entries")
        if not isinstance(entries_raw, list):
            raise ValueError("Invalid entries (expected list)")
        entries: list[ScratchIndexEntry] = []
        for raw in entries_raw:
            if not isinstance(raw, dict):
                raise ValueError("Invalid entry in index (expected mapping)")
            entries.append(
                ScratchIndexEntry(
                    entry_id=_require_str(raw.get("entry_id"), field="entry_id"),
                    title=_require_str(raw.get("title"), field="title"),
                    status=_require_str(raw.get("status"), field="status"),
                    created_at=_require_str(raw.get("created_at"), field="created_at"),
                    updated_at=_require_str(raw.get("updated_at"), field="updated_at"),
                    roadmap_item_id=raw.get("roadmap_item_id"),
                )
            )
        return ScratchIndex(schema=schema, generated_at=generated_at, entries=entries)


__all__ = [
    "SCRATCH_ENTRY_SCHEMA",
    "SCRATCH_INDEX_SCHEMA",
    "ScratchEntry",
    "ScratchIndex",
    "ScratchIndexEntry",
    "ScratchRoadmapLink",
]
