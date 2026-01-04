# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import yaml  # type: ignore[import-untyped]

from motus.atomic_io import atomic_write_text

BOOTSTRAP_RELEASE_VERSION = "0.0.0"

MOTUS_TREE_DIRS: tuple[str, ...] = (
    "releases",
    "user/skills",
    "user/standards",
    "user/config",
    "project/skills",
    "project/standards",
    "project/config",
    "state/ledger",
    "state/evidence",
    "state/orient",
    "state/orient-cache",
    "state/proposals",
    "state/locks",
)

DEFAULT_NAMESPACE_ACL_YAML = """\
# Namespace access control for coordination claim registry.
#
# This file is read by `motus claims ...` to isolate claims between workstreams.
# Patterns use fnmatch (e.g., "builder-*" matches "builder-2").
#
# Customize as needed for your org/project.
namespaces:
  motus-core:
    description: "Motus kernel and core features"
    agents:
      - pattern: "builder-*"
        permission: write
      - pattern: "codex-*"
        permission: write

  emmaus:
    description: "Project Emmaus workstream"
    agents:
      - pattern: "emmaus-*"
        permission: write

  vault:
    description: "Vault governance and CR process"
    agents:
      - pattern: "opus-*"
        permission: admin

global_admins:
  - pattern: "opus-*"
"""


@dataclass(frozen=True, slots=True)
class MotusLayout:
    root: Path

    @property
    def motus_dir(self) -> Path:
        return self.root / ".motus"

    @property
    def current_link(self) -> Path:
        return self.motus_dir / "current"

    @property
    def releases_dir(self) -> Path:
        return self.motus_dir / "releases"

    def release_dir(self, version: str) -> Path:
        return self.releases_dir / version

    def release_system_dir(self, version: str) -> Path:
        return self.release_dir(version) / "system"

    @property
    def project_config_dir(self) -> Path:
        return self.motus_dir / "project" / "config"


class MotusInitError(Exception):
    pass


def _utc_now_iso_z() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def find_packaged_release_dir() -> Path | None:
    """Optional: point to a packaged release without copying (lite mode).

    Configuration:
    - `MOTUS_PACKAGED_RELEASE_DIR`: directory to point `.motus/current` at.
    """

    raw = os.environ.get("MOTUS_PACKAGED_RELEASE_DIR")
    if not raw:
        return None
    p = Path(raw).expanduser().resolve()
    return p if p.exists() else None


def validate_motus_dir(motus_dir: Path) -> None:
    """Fail-closed validation for an existing `.motus/` directory."""

    if not motus_dir.exists():
        raise MotusInitError(f"missing .motus directory: {motus_dir}")
    if not motus_dir.is_dir():
        raise MotusInitError(f".motus exists but is not a directory: {motus_dir}")

    for rel in MOTUS_TREE_DIRS:
        p = motus_dir / rel
        if not p.exists():
            raise MotusInitError(f".motus exists but is missing required directory: {p}")
        if not p.is_dir():
            raise MotusInitError(f".motus contains non-directory where directory expected: {p}")

    current = motus_dir / "current"
    if not current.exists():
        raise MotusInitError(".motus exists but is missing required `current` pointer")
    if not current.is_symlink():
        raise MotusInitError(".motus `current` exists but is not a symlink (refusing to proceed)")


def create_motus_tree(motus_dir: Path) -> None:
    for rel in MOTUS_TREE_DIRS:
        (motus_dir / rel).mkdir(parents=True, exist_ok=True)

    namespace_acl_path = motus_dir / "project" / "config" / "namespace-acl.yaml"
    if not namespace_acl_path.exists():
        atomic_write_text(namespace_acl_path, DEFAULT_NAMESPACE_ACL_YAML)


def repair_motus_tree(motus_dir: Path) -> None:
    """Best-effort repair that only creates missing directories (no deletion)."""

    if motus_dir.exists() and not motus_dir.is_dir():
        raise MotusInitError(f".motus exists but is not a directory: {motus_dir}")
    motus_dir.mkdir(parents=True, exist_ok=True)

    for rel in MOTUS_TREE_DIRS:
        p = motus_dir / rel
        if p.exists() and not p.is_dir():
            raise MotusInitError(f".motus contains non-directory where directory expected: {p}")
        p.mkdir(parents=True, exist_ok=True)


def ensure_current_symlink(*, link: Path, target_dir: Path, force: bool) -> None:
    if not target_dir.exists():
        raise MotusInitError(f"release directory does not exist: {target_dir}")
    if not target_dir.is_dir():
        raise MotusInitError(f"release path is not a directory: {target_dir}")

    desired = Path(os.path.relpath(target_dir, start=link.parent))

    if link.exists() or link.is_symlink():
        if link.is_symlink():
            existing = Path(os.readlink(link))
            if existing == desired:
                return
            if not force:
                raise MotusInitError(
                    f".motus/current already exists and points elsewhere ({existing}); use --force to update"
                )
            link.unlink()
        else:
            raise MotusInitError(f".motus/current exists but is not a symlink: {link}")

    link.symlink_to(desired, target_is_directory=True)


def write_init_config_yaml(layout: MotusLayout, *, init_mode: str) -> Path:
    payload = {
        "vault_root": str(layout.root),
        "created_at": _utc_now_iso_z(),
        "init_mode": init_mode,
    }

    layout.project_config_dir.mkdir(parents=True, exist_ok=True)
    path = layout.project_config_dir / "init.yaml"
    content = yaml.safe_dump(payload, sort_keys=True)
    atomic_write_text(path, content)
    return path
