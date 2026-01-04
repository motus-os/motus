# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""CLI command: `motus orient` (Cached Orient lookup)."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import yaml
from rich.console import Console

from motus.cli.exit_codes import EXIT_SUCCESS, EXIT_USAGE
from motus.orient.analytics import compute_stats, render_table, top_high_miss
from motus.orient.api import OrientAPI
from motus.orient.fs_resolver import find_motus_dir
from motus.orient.index import StandardsIndex
from motus.orient.resolver import StandardsResolver
from motus.orient.telemetry import (
    append_orient_event,
    iter_orient_events,
    orient_events_path,
)
from motus.standards.schema import DecisionTypeRegistry

console = Console()
error_console = Console(stderr=True)


def _load_mapping_from_string(raw: str) -> dict[str, Any]:
    raw = raw.strip()
    if not raw:
        return {}

    # Prefer JSON when it looks like JSON.
    if raw[0] in ("{", "["):
        parsed = json.loads(raw)
    else:
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = yaml.safe_load(raw)

    if parsed is None:
        return {}
    if not isinstance(parsed, dict):
        raise ValueError("Expected a mapping (object) for context/constraints")
    return parsed


def _load_mapping_arg(arg: str | None) -> dict[str, Any]:
    if arg is None:
        if sys.stdin is not None and not sys.stdin.isatty():
            return _load_mapping_from_string(sys.stdin.read())
        raise ValueError("Missing --context (or provide via stdin)")

    if arg == "-":
        return _load_mapping_from_string(sys.stdin.read())

    maybe_path = Path(arg).expanduser()
    if maybe_path.exists() and maybe_path.is_file():
        return _load_mapping_from_string(maybe_path.read_text(encoding="utf-8"))

    return _load_mapping_from_string(arg)


def _load_registry(path: str | None) -> DecisionTypeRegistry | None:
    if path is None:
        motus_dir = find_motus_dir(Path.cwd())
        if motus_dir is None:
            return None

        candidates = [
            motus_dir / "project" / "config" / "decision_types.yaml",
            motus_dir / "user" / "config" / "decision_types.yaml",
            motus_dir / "config" / "decision_types.yaml",
        ]
        for candidate in candidates:
            if candidate.exists():
                path = candidate.as_posix()
                break
        else:
            return None

    p = Path(path).expanduser()
    if not p.exists():
        return None
    return DecisionTypeRegistry.load(p)


def orient_stats_command(args) -> int:
    motus_dir = find_motus_dir(Path.cwd())
    if motus_dir is None:
        error_console.print(
            "Not in a Motus workspace (missing .motus)",
            style="red",
            markup=False,
        )
        return EXIT_USAGE

    stats_path_arg = getattr(args, "stats_path", None)
    if stats_path_arg:
        path = Path(stats_path_arg).expanduser()
        events = (
            []
            if not path.exists()
            else [
                ev
                for ev in iter_orient_events_from_text(path.read_text(encoding="utf-8"))
            ]
        )
    else:
        events = list(iter_orient_events(motus_dir))
        path = orient_events_path(motus_dir)

    stats = compute_stats(events)

    min_calls = int(getattr(args, "min_calls", 1) or 1)
    if getattr(args, "high_miss", False):
        selected = top_high_miss(stats, limit=5, min_calls=min_calls)
    else:
        selected = [s for s in stats.values() if s.calls >= min_calls]
        selected.sort(key=lambda s: (-s.calls, s.decision_type))

    if getattr(args, "json", False):
        console.print(
            json.dumps(
                {
                    "events_path": path.as_posix(),
                    "decision_types": [s.to_dict() for s in selected],
                },
                indent=2,
                sort_keys=True,
            ),
            markup=False,
        )
    else:
        console.print(render_table(selected), markup=False)

    return EXIT_SUCCESS


def iter_orient_events_from_text(text: str):
    from motus.orient.telemetry import iter_orient_events_from_lines

    return iter_orient_events_from_lines(text.splitlines())


def orient_command(args) -> int:
    """Argparse-dispatched handler for `motus orient`."""

    decision_type = getattr(args, "decision_type", None)
    if decision_type == "stats":
        return orient_stats_command(args)

    try:
        context = _load_mapping_arg(getattr(args, "context", None))
        constraints_arg = getattr(args, "constraints", None)
        constraints = _load_mapping_arg(constraints_arg) if constraints_arg is not None else None
    except Exception as e:
        error_console.print(str(e), style="red", markup=False)
        return EXIT_USAGE

    if not decision_type:
        error_console.print("Missing <decision_type>", style="red", markup=False)
        return EXIT_USAGE

    registry = None
    try:
        registry = _load_registry(getattr(args, "registry", None))
    except Exception as e:
        error_console.print(
            f"Failed to load decision type registry: {e}",
            style="red",
            markup=False,
        )
        return EXIT_USAGE

    resolver = None
    motus_dir = find_motus_dir(Path.cwd())
    if motus_dir is not None:
        rebuild_index = bool(getattr(args, "rebuild_index", False))
        index = StandardsIndex.load_or_build(motus_dir, rebuild=rebuild_index)
        resolver = StandardsResolver(index=index)

    api = OrientAPI(resolver=resolver, decision_types=registry)
    explain = bool(getattr(args, "explain", False))

    try:
        result = api.orient(decision_type, context, constraints=constraints, explain=explain)
    except Exception as e:
        error_console.print(f"Orient failed: {e}", style="red", markup=False)
        return EXIT_USAGE

    # Best-effort local telemetry to support `motus orient stats`.
    # Telemetry must never change lookup behavior or exit codes.
    if motus_dir is not None:
        try:
            append_orient_event(
                motus_dir,
                decision_type=decision_type,
                result=result.result,
                standard_id=result.standard_id,
                layer=result.layer,
            )
        except Exception:
            pass
    console.print(
        json.dumps(result.to_dict(include_trace=explain), indent=2, sort_keys=True),
        markup=False,
    )

    if result.result == "CONFLICT":
        return EXIT_USAGE
    return EXIT_SUCCESS
