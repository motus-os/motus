# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""CLI command: `motus gates` (release gate registry)."""

from __future__ import annotations

import json
import os
from argparse import Namespace
from importlib import resources
from pathlib import Path
from typing import Any

import yaml
from rich.console import Console
from rich.table import Table

from motus.cli.exit_codes import EXIT_SUCCESS, EXIT_USAGE

console = Console()
error_console = Console(stderr=True)


def _repo_root() -> Path:
    cwd = Path.cwd()
    if (cwd / "packages" / "cli").exists():
        return cwd
    if (cwd / "pyproject.toml").exists() and cwd.name == "cli":
        return cwd.parent.parent
    return cwd


def _resolve_registry_path(args: Namespace) -> tuple[Path, bool]:
    override = (getattr(args, "registry", None) or "").strip()
    if override:
        return Path(override).expanduser().resolve(), True

    env_path = os.environ.get("MOTUS_GATES_REGISTRY", "").strip()
    if env_path:
        return Path(env_path).expanduser().resolve(), True

    return _repo_root() / "packages" / "cli" / "docs" / "standards" / "gates.yaml", False


def _load_registry(path: Path, *, strict: bool) -> dict[str, Any]:
    if path.exists():
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    else:
        if strict:
            raise ValueError(f"Gate registry not found: {path}")
        try:
            data_text = (
                resources.files("motus.data")
                .joinpath("gates.yaml")
                .read_text(encoding="utf-8")
            )
        except Exception as exc:
            raise ValueError(f"Gate registry not found: {path}") from exc
        data = yaml.safe_load(data_text) or {}
    if not isinstance(data, dict):
        raise ValueError("Gate registry must be a mapping")
    return data


def _normalize_gate(raw: dict[str, Any]) -> dict[str, Any]:
    gate_id = str(raw.get("id", "")).strip()
    if not gate_id:
        raise ValueError("Gate entry missing id")
    description = str(raw.get("description", "")).strip()
    tier = str(raw.get("tier", "")).strip()
    kind = str(raw.get("kind", "")).strip()
    command = str(raw.get("command", "")).strip()
    required = bool(raw.get("required", True))
    return {
        "id": gate_id,
        "description": description,
        "tier": tier,
        "kind": kind,
        "command": command,
        "required": required,
    }


def _collect_gates(registry: dict[str, Any]) -> list[dict[str, Any]]:
    gates_raw = registry.get("gates", [])
    if not isinstance(gates_raw, list):
        raise ValueError("gates must be a list")
    gates: list[dict[str, Any]] = []
    for entry in gates_raw:
        if not isinstance(entry, dict):
            raise ValueError("gates entries must be mappings")
        gates.append(_normalize_gate(entry))
    return gates


def gates_list_command(args: Namespace) -> int:
    """Argparse-dispatched handler for `motus gates list`."""

    try:
        registry_path, strict = _resolve_registry_path(args)
        registry = _load_registry(registry_path, strict=strict)
        gates = _collect_gates(registry)
    except Exception as exc:
        error_console.print(str(exc), style="red", markup=False)
        return EXIT_USAGE

    json_mode = bool(getattr(args, "json", False))
    if json_mode:
        payload = {
            "registry_version": str(registry.get("version", "")),
            "gates": gates,
            "count": len(gates),
        }
        console.print(json.dumps(payload, indent=2, sort_keys=True), markup=False)
        return EXIT_SUCCESS

    table = Table(title="Motus Gates", show_lines=False)
    table.add_column("ID", style="dim")
    table.add_column("Tier")
    table.add_column("Kind")
    table.add_column("Required")
    table.add_column("Command", style="dim")

    for gate in gates:
        table.add_row(
            gate.get("id", ""),
            gate.get("tier", ""),
            gate.get("kind", ""),
            "yes" if gate.get("required") else "no",
            gate.get("command", ""),
        )

    console.print(table)
    return EXIT_SUCCESS


def gates_show_command(args: Namespace) -> int:
    """Argparse-dispatched handler for `motus gates show`."""

    gate_id = (getattr(args, "gate_id", None) or "").strip()
    if not gate_id:
        error_console.print("Gate id required", style="red", markup=False)
        return EXIT_USAGE

    try:
        registry_path, strict = _resolve_registry_path(args)
        registry = _load_registry(registry_path, strict=strict)
        gates = _collect_gates(registry)
    except Exception as exc:
        error_console.print(str(exc), style="red", markup=False)
        return EXIT_USAGE

    match = next((g for g in gates if g.get("id") == gate_id), None)
    if not match:
        error_console.print(f"Gate not found: {gate_id}", style="red", markup=False)
        return EXIT_USAGE

    json_mode = bool(getattr(args, "json", False))
    if json_mode:
        console.print(json.dumps(match, indent=2, sort_keys=True), markup=False)
        return EXIT_SUCCESS

    table = Table(title=f"Gate {gate_id}", show_lines=False)
    table.add_column("Field", style="dim")
    table.add_column("Value")
    for key in ("description", "tier", "kind", "required", "command"):
        value = match.get(key, "")
        if isinstance(value, bool):
            value = "yes" if value else "no"
        table.add_row(key, str(value))

    console.print(table)
    return EXIT_SUCCESS
