# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Standards index for Cached Orient.

The index is an on-disk snapshot of parsed standards to avoid re-parsing YAML on
every lookup. Rebuild is explicit: callers should rebuild after editing
standards.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Mapping

from motus.atomic_io import atomic_write_json
from motus.standards.schema import Standard
from motus.orient.standards_cache import load_standard_yaml

Layer = Literal["user", "project", "system"]

INDEX_SCHEMA_VERSION = 1
MAX_STANDARD_FILES = int(os.environ.get("MC_STANDARDS_MAX_FILES", "2000"))
MAX_STANDARD_DEPTH = int(os.environ.get("MC_STANDARDS_MAX_DEPTH", "6"))


def infer_layer(path: Path) -> Layer:
    """Infer layer from filesystem path (fail-closed)."""

    path_str = str(path)
    if "/current/system/" in path_str or "/releases/" in path_str:
        return "system"
    if "/user/" in path_str:
        return "user"
    if "/project/" in path_str:
        return "project"
    raise ValueError(f"Cannot infer layer from {path}")


def _iter_standard_files(base: Path) -> list[Path]:
    if not base.exists() or not base.is_dir():
        return []
    root = base.resolve()
    root_depth = len(root.parts)
    files: list[Path] = []
    for current_root, dirs, filenames in os.walk(root):
        depth = len(Path(current_root).parts) - root_depth
        if depth >= MAX_STANDARD_DEPTH:
            dirs[:] = []
        for name in filenames:
            if name != "standard.yaml":
                continue
            files.append(Path(current_root) / name)
            if len(files) >= MAX_STANDARD_FILES:
                raise ValueError("Too many standards files for index scan")
    return sorted(files)


def _require_mapping(raw: Any, *, path: Path) -> Mapping[str, Any]:
    if not isinstance(raw, Mapping):
        raise ValueError(f"Invalid standard (expected mapping): {path}")
    return raw


def _require_str(raw: Any, *, field: str, path: Path) -> str:
    if not isinstance(raw, str) or not raw:
        raise ValueError(f"Invalid standard ({field} must be non-empty string): {path}")
    return raw


def _require_dict(raw: Any, *, field: str, path: Path) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError(f"Invalid standard ({field} must be mapping): {path}")
    return raw


def _standard_to_dict(s: Standard) -> dict[str, Any]:
    return {
        "id": s.id,
        "type": s.type,
        "version": s.version,
        "applies_if": s.applies_if,
        "output": s.output,
        "layer": s.layer,
        "status": s.status,
        "priority": s.priority,
        "tests": s.tests,
        "rationale": s.rationale,
    }


def _standard_from_dict(d: Mapping[str, Any], *, path: Path) -> Standard:
    # Fail-closed: keep parsing strict and stable.
    return Standard(
        id=_require_str(d.get("id"), field="id", path=path),
        type=_require_str(d.get("type"), field="type", path=path),
        version=_require_str(d.get("version"), field="version", path=path),
        applies_if=_require_dict(d.get("applies_if") or {}, field="applies_if", path=path),
        output=_require_dict(d.get("output") or {}, field="output", path=path),
        layer=str(d.get("layer") or "project"),
        status=str(d.get("status") or "active"),
        priority=int(d.get("priority") or 0),
        tests=list(d.get("tests") or []) or None,
        rationale=(str(d["rationale"]) if "rationale" in d and d["rationale"] is not None else None),
    )


@dataclass(frozen=True, slots=True)
class IndexedStandard:
    standard: Standard
    path: Path

    @property
    def inferred_layer(self) -> Layer:
        return infer_layer(self.path)


@dataclass(frozen=True, slots=True)
class StandardsIndex:
    """Immutable standards index snapshot."""

    motus_dir: Path
    standards_by_type: dict[str, tuple[IndexedStandard, ...]]
    schema_version: int = INDEX_SCHEMA_VERSION

    @property
    def index_path(self) -> Path:
        return self.motus_dir / "state" / "orient-cache" / "index.json"

    def get_standards(self, decision_type: str) -> tuple[IndexedStandard, ...]:
        return self.standards_by_type.get(decision_type, ())

    def to_dict(self) -> dict[str, Any]:
        rows: list[dict[str, Any]] = []
        for decision_type in sorted(self.standards_by_type.keys()):
            for item in self.standards_by_type[decision_type]:
                rows.append(
                    {
                        "path": item.path.as_posix(),
                        "standard": _standard_to_dict(item.standard),
                    }
                )

        return {
            "schema_version": self.schema_version,
            "standards": rows,
        }

    def write(self) -> Path:
        atomic_write_json(self.index_path, self.to_dict(), indent=2, sort_keys=True)
        return self.index_path

    @classmethod
    def load(cls, motus_dir: Path) -> StandardsIndex:
        index_path = motus_dir / "state" / "orient-cache" / "index.json"
        raw = json.loads(index_path.read_text(encoding="utf-8"))

        raw_map = _require_mapping(raw, path=index_path)
        if int(raw_map.get("schema_version") or 0) != INDEX_SCHEMA_VERSION:
            raise ValueError(f"Unsupported standards index schema_version: {raw_map.get('schema_version')}")

        raw_standards = raw_map.get("standards")
        if not isinstance(raw_standards, list):
            raise ValueError("Standards index must contain a 'standards' list")

        by_type: dict[str, list[IndexedStandard]] = {}
        for entry in raw_standards:
            if not isinstance(entry, Mapping):
                raise ValueError("Invalid standards index entry (expected mapping)")
            raw_path = entry.get("path")
            if not isinstance(raw_path, str) or not raw_path:
                raise ValueError("Invalid standards index entry (missing/invalid path)")
            p = Path(raw_path)
            s_raw = entry.get("standard")
            s_map = _require_mapping(s_raw, path=p)
            s = _standard_from_dict(s_map, path=p)

            by_type.setdefault(s.type, []).append(IndexedStandard(standard=s, path=p))

        frozen: dict[str, tuple[IndexedStandard, ...]] = {}
        for decision_type, items in by_type.items():
            frozen[decision_type] = tuple(
                sorted(items, key=lambda i: (i.standard.standard_id, i.path.as_posix()))
            )

        return cls(motus_dir=motus_dir, standards_by_type=frozen)

    @classmethod
    def build_from_fs(cls, motus_dir: Path) -> StandardsIndex:
        roots = [
            motus_dir / "user" / "standards",
            motus_dir / "project" / "standards",
            motus_dir / "current" / "system" / "standards",
        ]

        by_type: dict[str, list[IndexedStandard]] = {}
        for root in roots:
            for path in _iter_standard_files(root):
                raw = load_standard_yaml(path)
                m = _require_mapping(raw, path=path)

                # Fail-closed: require core keys even if schema evolves.
                s = Standard(
                    id=_require_str(m.get("id"), field="id", path=path),
                    type=_require_str(m.get("type"), field="type", path=path),
                    version=_require_str(m.get("version"), field="version", path=path),
                    applies_if=_require_dict(m.get("applies_if") or {}, field="applies_if", path=path),
                    output=_require_dict(m.get("output") or {}, field="output", path=path),
                    layer=str(m.get("layer") or "project"),
                    status=str(m.get("status") or "active"),
                    priority=int(m.get("priority") or 0),
                    tests=list(m.get("tests") or []) or None,
                    rationale=(str(m["rationale"]) if "rationale" in m and m["rationale"] is not None else None),
                )

                # Ensure layer inference is valid; refuse to index unknown layouts.
                _ = infer_layer(path)
                by_type.setdefault(s.type, []).append(IndexedStandard(standard=s, path=path))

        frozen: dict[str, tuple[IndexedStandard, ...]] = {}
        for decision_type, items in by_type.items():
            frozen[decision_type] = tuple(
                sorted(items, key=lambda i: (i.standard.standard_id, i.path.as_posix()))
            )

        return cls(motus_dir=motus_dir, standards_by_type=frozen)

    @classmethod
    def load_or_build(cls, motus_dir: Path, *, rebuild: bool = False) -> StandardsIndex:
        index_path = motus_dir / "state" / "orient-cache" / "index.json"
        if rebuild or not index_path.exists():
            index = cls.build_from_fs(motus_dir)
            index.write()
            return index
        return cls.load(motus_dir)
