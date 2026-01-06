# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""CLI command: `motus modules` (module registry)."""

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

from motus.cli.exit_codes import EXIT_ERROR, EXIT_SUCCESS, EXIT_USAGE

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

    env_path = os.environ.get("MOTUS_MODULE_REGISTRY", "").strip()
    if env_path:
        return Path(env_path).expanduser().resolve(), True

    return (
        _repo_root() / "packages" / "cli" / "docs" / "standards" / "module-registry.yaml",
        False,
    )


def _load_registry(path: Path, *, strict: bool) -> dict[str, Any]:
    if path.exists():
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    else:
        if strict:
            raise ValueError(f"Module registry not found: {path}")
        try:
            data_text = (
                resources.files("motus.data")
                .joinpath("module-registry.yaml")
                .read_text(encoding="utf-8")
            )
        except Exception as exc:
            raise ValueError(f"Module registry not found: {path}") from exc
        data = yaml.safe_load(data_text) or {}
    if not isinstance(data, dict):
        raise ValueError("Module registry must be a mapping")
    return data


def _normalize_module(raw: dict[str, Any], *, default_scope: str) -> dict[str, Any]:
    module_id = str(raw.get("id", "")).strip()
    if not module_id:
        raise ValueError("Module entry missing id")
    name = str(raw.get("marketing_name") or raw.get("name") or module_id).strip()
    status = str(raw.get("status", "")).strip()
    scope = str(raw.get("scope") or default_scope).strip()
    description = str(raw.get("description", "")).strip()
    return {
        "id": module_id,
        "name": name,
        "status": status or "unknown",
        "scope": scope or default_scope,
        "roadmap_id": raw.get("roadmap_id"),
        "target_release": raw.get("target_release"),
        "description": description,
    }


def _collect_modules(registry: dict[str, Any]) -> list[dict[str, Any]]:
    modules: list[dict[str, Any]] = []
    kernel = registry.get("kernel")
    if isinstance(kernel, dict):
        modules.append(_normalize_module(kernel, default_scope="kernel"))

    bundled = registry.get("bundled_modules") or []
    if not isinstance(bundled, list):
        raise ValueError("bundled_modules must be a list")
    for entry in bundled:
        if not isinstance(entry, dict):
            raise ValueError("bundled_modules entries must be mappings")
        modules.append(_normalize_module(entry, default_scope="bundled"))

    return modules


def modules_list_command(args: Namespace) -> int:
    """Argparse-dispatched handler for `motus modules list`."""

    try:
        registry_path, strict = _resolve_registry_path(args)
        registry = _load_registry(registry_path, strict=strict)
        modules = _collect_modules(registry)
    except Exception as exc:
        error_console.print(str(exc), style="red", markup=False)
        return EXIT_USAGE

    json_mode = bool(getattr(args, "json", False))
    if json_mode:
        payload = {
            "registry_version": str(registry.get("version", "")),
            "modules": modules,
            "count": len(modules),
        }
        console.print(json.dumps(payload, indent=2, sort_keys=True), markup=False)
        return EXIT_SUCCESS

    table = Table(title="Motus Modules", show_lines=False)
    table.add_column("ID", style="dim")
    table.add_column("Name")
    table.add_column("Status")
    table.add_column("Version")
    table.add_column("Scope")
    table.add_column("Roadmap", style="dim")

    for module in modules:
        target_release = module.get("target_release") or "-"
        roadmap_id = module.get("roadmap_id") or "-"
        table.add_row(
            module.get("id", ""),
            module.get("name", ""),
            module.get("status", ""),
            str(target_release),
            module.get("scope", ""),
            str(roadmap_id),
        )

    console.print(table)
    return EXIT_SUCCESS
