# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Path resolution helpers for the .mc -> .motus transition."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

CANONICAL_DIRNAME = ".motus"
LEGACY_DIRNAME = ".mc"
LEGACY_REMOVAL_VERSION = "v0.2.0"


@dataclass(frozen=True, slots=True)
class WorkspaceResolution:
    path: Path
    is_legacy: bool


def check_legacy_path() -> str | None:
    """Return a deprecation warning if ~/.mc/ exists."""
    legacy = Path.home() / LEGACY_DIRNAME
    if legacy.exists():
        return (
            "DEPRECATION: ~/.mc/ detected. Motus now uses ~/.motus/ as the canonical path. "
            "Run `motus db migrate-path` to migrate. "
            f"Support for ~/.mc/ will be removed in {LEGACY_REMOVAL_VERSION}."
        )
    return None


def legacy_workspace_warning(legacy_dir: Path) -> str:
    """Format a warning message for legacy workspace directories."""
    return (
        f"DEPRECATION: legacy workspace path {legacy_dir} detected. "
        "Motus now uses .motus/. Run `motus db migrate-path` from the repo root to migrate. "
        f"Support for .mc/ will be removed in {LEGACY_REMOVAL_VERSION}."
    )


def resolve_state_dir() -> Path:
    """Resolve the global Motus state directory with legacy fallback."""
    canonical = Path.home() / CANONICAL_DIRNAME
    legacy = Path.home() / LEGACY_DIRNAME
    if canonical.exists():
        return canonical
    if legacy.exists():
        return legacy
    return canonical


def resolve_workspace_dir(root: Path, *, create: bool = False) -> WorkspaceResolution:
    """Resolve the workspace dir under root, preferring .motus over .mc."""
    root = root.expanduser().resolve()
    canonical = root / CANONICAL_DIRNAME
    legacy = root / LEGACY_DIRNAME

    if canonical.exists() and canonical.is_dir():
        return WorkspaceResolution(path=canonical, is_legacy=False)
    if legacy.exists() and legacy.is_dir():
        return WorkspaceResolution(path=legacy, is_legacy=True)

    if create:
        canonical.mkdir(parents=True, exist_ok=True)
    return WorkspaceResolution(path=canonical, is_legacy=False)


def find_workspace_dir(start: Path) -> WorkspaceResolution | None:
    """Find the nearest workspace directory (.motus or legacy .mc)."""
    cur = start.expanduser().resolve()
    candidates: Iterable[Path] = [cur, *cur.parents]
    for base in candidates:
        canonical = base / CANONICAL_DIRNAME
        if canonical.exists() and canonical.is_dir():
            return WorkspaceResolution(path=canonical, is_legacy=False)
        legacy = base / LEGACY_DIRNAME
        if legacy.exists() and legacy.is_dir():
            return WorkspaceResolution(path=legacy, is_legacy=True)
    return None


def find_legacy_workspace_dir(start: Path) -> Path | None:
    """Find the nearest legacy .mc directory walking upwards from start."""
    cur = start.expanduser().resolve()
    candidates: Iterable[Path] = [cur, *cur.parents]
    for base in candidates:
        legacy = base / LEGACY_DIRNAME
        if legacy.exists() and legacy.is_dir():
            return legacy
    return None
