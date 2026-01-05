# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Filesystem-backed resolver for Cached Orient (v0).

This resolver loads `standard.yaml` files from a Motus workspace `.motus/` tree:
- `.motus/user/standards/<type>/**/standard.yaml`
- `.motus/project/standards/<type>/**/standard.yaml`
- `.motus/current/system/standards/<type>/**/standard.yaml`

Resolution (v0):
- Predicate match is exact (supports scalar or list values)
- Specificity = number of predicate keys
- Priority breaks specificity ties
- Layer precedence breaks remaining ties (user > project > system)
- Unresolvable ties => CONFLICT (fail-closed)
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Literal

from motus.orient.result import OrientResult
from motus.orient.standards_cache import load_standard_yaml

Layer = Literal["user", "project", "system"]
MAX_STANDARD_FILES = int(os.environ.get("MC_STANDARDS_MAX_FILES", "2000"))
MAX_STANDARD_DEPTH = int(os.environ.get("MC_STANDARDS_MAX_DEPTH", "6"))


def find_motus_dir(start: Path) -> Path | None:
    """Find the nearest `.motus` directory walking upwards from start."""

    cur = start.expanduser().resolve()
    candidates: Iterable[Path] = [cur, *cur.parents]
    for base in candidates:
        motus_dir = base / ".motus"
        if motus_dir.exists() and motus_dir.is_dir():
            return motus_dir
    return None


def _predicate_matches(applies_if: dict[str, Any], context: dict[str, Any]) -> bool:
    for key, required in applies_if.items():
        if key not in context:
            return False
        actual = context[key]
        if isinstance(required, list):
            if actual not in required:
                return False
        else:
            if actual != required:
                return False
    return True


def _iter_standard_files(layer_dir: Path) -> list[Path]:
    if not layer_dir.exists() or not layer_dir.is_dir():
        return []
    root = layer_dir.resolve()
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
                raise ValueError("Too many standards files for resolver scan")
    return sorted(files)


@dataclass(frozen=True, slots=True)
class FilesystemStandardsResolverV0:
    motus_dir: Path

    def resolve(
        self,
        *,
        decision_type: str,
        context: dict[str, Any],
        constraints: dict[str, Any] | None = None,
        explain: bool = False,
    ) -> OrientResult:
        _ = constraints  # reserved for future phases

        layers: list[tuple[Layer, Path]] = [
            ("user", self.motus_dir / "user" / "standards" / decision_type),
            ("project", self.motus_dir / "project" / "standards" / decision_type),
            ("system", self.motus_dir / "current" / "system" / "standards" / decision_type),
        ]

        scanned: dict[str, int] = {}
        matches: list[dict[str, Any]] = []

        for layer, base in layers:
            standard_files = _iter_standard_files(base)
            scanned[layer] = len(standard_files)

            for path in standard_files:
                raw = load_standard_yaml(path)
                if not isinstance(raw, dict):
                    raise ValueError(f"Invalid standard (expected mapping): {path}")

                # Fail-closed on malformed standards.
                for key in ("id", "type", "version", "applies_if", "output"):
                    if key not in raw:
                        raise ValueError(f"Invalid standard (missing '{key}'): {path}")

                if str(raw["type"]) != decision_type:
                    continue

                applies_if = raw.get("applies_if") or {}
                if not isinstance(applies_if, dict):
                    raise ValueError(f"Invalid standard (applies_if must be mapping): {path}")
                if not _predicate_matches(applies_if, context):
                    continue

                output = raw.get("output") or {}
                if not isinstance(output, dict):
                    raise ValueError(f"Invalid standard (output must be mapping): {path}")

                priority = int(raw.get("priority") or 0)
                specificity = len(applies_if.keys())

                matches.append(
                    {
                        "standard_id": f"{raw['id']}@{raw['version']}",
                        "id": str(raw["id"]),
                        "version": str(raw["version"]),
                        "layer": layer,
                        "priority": priority,
                        "specificity": specificity,
                        "path": path.as_posix(),
                        "output": output,
                    }
                )

        if not matches:
            return OrientResult(
                result="MISS",
                match_trace=(
                    {"decision_type": decision_type, "context": context, "scanned": scanned}
                    if explain
                    else None
                ),
            )

        max_spec = max(m["specificity"] for m in matches)
        candidates = [m for m in matches if m["specificity"] == max_spec]

        max_pri = max(m["priority"] for m in candidates)
        candidates = [m for m in candidates if m["priority"] == max_pri]

        if len(candidates) == 1:
            winner = candidates[0]
            trace = None
            if explain:
                trace = {
                    "decision_type": decision_type,
                    "context": context,
                    "scanned": scanned,
                    "matched": [
                        {k: v for k, v in m.items() if k != "output"} for m in sorted(matches, key=lambda x: x["standard_id"])
                    ],
                }
            return OrientResult(
                result="HIT",
                decision=winner["output"],
                standard_id=winner["standard_id"],
                layer=winner["layer"],
                match_trace=trace,
            )

        # Layer precedence tie-breaker (user > project > system)
        for layer in ("user", "project", "system"):
            layer_hits = [c for c in candidates if c["layer"] == layer]
            if len(layer_hits) == 1:
                winner = layer_hits[0]
                trace = None
                if explain:
                    trace = {
                        "decision_type": decision_type,
                        "context": context,
                        "scanned": scanned,
                        "candidates": [
                            {k: v for k, v in m.items() if k != "output"} for m in sorted(candidates, key=lambda x: x["standard_id"])
                        ],
                    }
                return OrientResult(
                    result="HIT",
                    decision=winner["output"],
                    standard_id=winner["standard_id"],
                    layer=winner["layer"],
                    match_trace=trace,
                )
            if len(layer_hits) > 1:
                break

        trace = None
        if explain:
            trace = {
                "decision_type": decision_type,
                "context": context,
                "scanned": scanned,
                "candidates": [
                    {k: v for k, v in m.items() if k != "output"} for m in sorted(candidates, key=lambda x: x["standard_id"])
                ],
            }

        return OrientResult(
            result="CONFLICT",
            candidates=[
                {k: v for k, v in m.items() if k != "output"} for m in sorted(candidates, key=lambda x: x["standard_id"])
            ],
            match_trace=trace,
        )
