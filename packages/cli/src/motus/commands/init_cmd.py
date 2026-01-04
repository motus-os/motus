# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

from __future__ import annotations

from argparse import Namespace
from pathlib import Path

from rich.console import Console

from motus.motus_fs import (
    BOOTSTRAP_RELEASE_VERSION,
    MotusLayout,
    create_motus_tree,
    ensure_current_symlink,
    find_packaged_release_dir,
    repair_motus_tree,
    validate_motus_dir,
    write_init_config_yaml,
)


def init_command(args: Namespace) -> None:
    """Initialize a Motus workspace (.motus/ skeleton)."""

    integrate_path = getattr(args, "integrate", None)
    mode = "integrate" if integrate_path else ("full" if getattr(args, "full", False) else "lite")

    root = Path(integrate_path).expanduser().resolve() if integrate_path else Path(args.path).resolve()
    layout = MotusLayout(root=root)
    console = Console()

    if layout.motus_dir.exists():
        if getattr(args, "force", False):
            repair_motus_tree(layout.motus_dir)
        else:
            validate_motus_dir(layout.motus_dir)
            console.print(f"Already initialized: {root}", markup=False)
            return
    else:
        create_motus_tree(layout.motus_dir)

    packaged_release_dir = find_packaged_release_dir() if mode == "lite" else None
    if packaged_release_dir is not None:
        target_release_dir = packaged_release_dir
    else:
        target_release_dir = layout.release_dir(BOOTSTRAP_RELEASE_VERSION)
        layout.release_system_dir(BOOTSTRAP_RELEASE_VERSION).mkdir(parents=True, exist_ok=True)

    ensure_current_symlink(
        link=layout.current_link,
        target_dir=target_release_dir,
        force=getattr(args, "force", False),
    )

    init_config_path: Path | None = None
    if mode == "integrate":
        init_config_path = write_init_config_yaml(layout, init_mode="integrate")

    current_target = layout.current_link.resolve()

    console.print("Initialized Motus workspace:", markup=False)
    console.print(f"  Root: {root}", markup=False)
    console.print(f"  Mode: {mode}", markup=False)
    console.print(f"  Motus: {layout.motus_dir}", markup=False)
    console.print(f"  Current: {current_target}", markup=False)
    if packaged_release_dir is not None:
        console.print(f"  PackagedRelease: {packaged_release_dir}", markup=False)
    if init_config_path is not None:
        console.print(f"  ProjectConfig: {init_config_path}", markup=False)
