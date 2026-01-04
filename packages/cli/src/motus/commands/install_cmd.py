# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Agent onboarding install command."""

from __future__ import annotations

from argparse import Namespace

from rich.console import Console

from motus.config_loader import get_config_path, load_config, save_config


def install_command(_: Namespace | None = None) -> None:
    """Install agent onboarding scaffolding and enable protocol defaults."""

    console = Console()

    console.print("[bold]Motus agent onboarding[/bold]")
    console.print("\nDocumentation:", markup=False)
    console.print("  https://github.com/motus-os/motus", markup=False)

    config = load_config()
    config.motus_enabled = True
    config.protocol_enforcement = "strict"
    save_config(config)

    console.print("\nConfig updated:", markup=False)
    console.print(f"  motus_enabled = {config.motus_enabled}", markup=False)
    console.print(f"  protocol_enforcement = {config.protocol_enforcement}", markup=False)
    console.print(f"  Path: {get_config_path()}", markup=False)
