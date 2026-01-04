# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""CLI command: `motus verify clean`."""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from rich.console import Console

from motus.cli.exit_codes import EXIT_ERROR, EXIT_SUCCESS, EXIT_USAGE

console = Console()


def _resolve_source_repo(source: str | None) -> Path | None:
    if source:
        path = Path(source).expanduser().resolve()
        return path if path.exists() else None

    try:
        proc = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=str(Path.cwd()),
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return None

    if proc.returncode != 0:
        return None
    root = proc.stdout.strip()
    if not root:
        return None
    path = Path(root)
    return path if path.exists() else None


def _venv_bin(venv_dir: Path) -> Path:
    unix_bin = venv_dir / "bin"
    if unix_bin.exists():
        return unix_bin
    return venv_dir / "Scripts"


def verify_clean_command(args) -> int:
    source = _resolve_source_repo(getattr(args, "source", None))
    if source is None:
        console.print("[red]Unable to locate git repository root[/red]")
        return EXIT_USAGE

    keep_temp = bool(getattr(args, "keep_temp", False))
    skip_security = bool(getattr(args, "skip_security", False))

    temp_dir = None
    temp_ctx = None
    if keep_temp:
        temp_dir = Path(tempfile.mkdtemp(prefix="motus-clean-"))
    else:
        temp_ctx = tempfile.TemporaryDirectory(prefix="motus-clean-")
        temp_dir = Path(temp_ctx.name)

    try:
        console.print(f"Cloning {source} into {temp_dir}")
        clone_proc = subprocess.run(
            ["git", "clone", "--quiet", str(source), str(temp_dir)],
            check=False,
        )
        if clone_proc.returncode != 0:
            console.print("[red]git clone failed[/red]")
            return EXIT_ERROR

        cli_root = temp_dir / "packages" / "cli"
        if not cli_root.exists():
            console.print("[red]packages/cli not found in clone[/red]")
            return EXIT_ERROR

        venv_dir = temp_dir / ".venv"
        create_proc = subprocess.run(
            [sys.executable, "-m", "venv", str(venv_dir)],
            check=False,
        )
        if create_proc.returncode != 0:
            console.print("[red]venv creation failed[/red]")
            return EXIT_ERROR

        bin_dir = _venv_bin(venv_dir)
        pip_path = bin_dir / "pip"
        python_path = bin_dir / "python"

        upgrade_proc = subprocess.run(
            [str(pip_path), "install", "--upgrade", "pip", "setuptools"],
            check=False,
        )
        if upgrade_proc.returncode != 0:
            console.print("[red]pip upgrade failed[/red]")
            return EXIT_ERROR

        install_proc = subprocess.run(
            [str(pip_path), "install", "-e", ".[dev,mcp]"],
            cwd=str(cli_root),
            check=False,
        )
        if install_proc.returncode != 0:
            console.print("[red]pip install -e failed[/red]")
            return EXIT_ERROR

        cmd = [
            str(python_path),
            "scripts/ci/health_ledger.py",
            "--output",
            "artifacts/health.json",
        ]
        if skip_security:
            cmd.append("--skip-security")

        health_proc = subprocess.run(cmd, cwd=str(cli_root), check=False)
        if health_proc.returncode != 0:
            return health_proc.returncode

        console.print("Clean verification succeeded", style="green")
        return EXIT_SUCCESS
    finally:
        if temp_ctx is not None:
            temp_ctx.cleanup()
        elif not keep_temp and temp_dir is not None and temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)
        elif keep_temp and temp_dir is not None:
            console.print(f"Temp retained at {temp_dir}")
