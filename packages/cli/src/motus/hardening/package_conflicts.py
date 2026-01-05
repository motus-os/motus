# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Detect conflicting Motus package installations."""

from __future__ import annotations

from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path


CONFLICTING_DISTS = ("motus", "motus-command")


@dataclass(frozen=True)
class PackageConflictResult:
    conflict: bool
    conflicts: dict[str, str]
    origin: str | None
    shadowed: bool


def detect_package_conflicts() -> PackageConflictResult:
    """Return details about conflicting Motus package installations."""
    conflicts: dict[str, str] = {}
    for dist in CONFLICTING_DISTS:
        try:
            conflicts[dist] = version(dist)
        except PackageNotFoundError:
            continue

    origin = None
    shadowed = False
    try:
        import motus as motus_pkg  # type: ignore

        origin = str(Path(motus_pkg.__file__).resolve())
        shadowed = "motus-command" in origin
    except Exception:
        pass

    return PackageConflictResult(
        conflict=bool(conflicts) or shadowed,
        conflicts=conflicts,
        origin=origin,
        shadowed=shadowed,
    )
