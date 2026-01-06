#!/usr/bin/env python3
"""Validate the canonical release gate registry."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[4]
REGISTRY_PATH = ROOT / "packages" / "cli" / "docs" / "standards" / "gates.yaml"
RUN_ALL_PATH = ROOT / "scripts" / "gates" / "run-all-gates.sh"

GATE_ID_RE = re.compile(r"^GATE-[A-Z]+-[0-9]+$")
ALLOWED_TIERS = {"T0", "T1", "T2", "T3"}
ALLOWED_KINDS = {"intake", "test", "security", "plan", "artifact", "egress"}


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Missing gate registry: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError("Gate registry must be a mapping")
    return data


def _extract_run_all_gate_ids() -> set[str]:
    if not RUN_ALL_PATH.exists():
        return set()
    pattern = re.compile(r'run_gate\s+"(?P<gate>GATE-[A-Z]+-[0-9]+)"')
    gate_ids: set[str] = set()
    for line in RUN_ALL_PATH.read_text(encoding="utf-8").splitlines():
        match = pattern.search(line)
        if match:
            gate_ids.add(match.group("gate"))
    return gate_ids


def _validate_registry(data: dict[str, Any], errors: list[str]) -> set[str]:
    version = str(data.get("version", "")).strip()
    if not version:
        errors.append("registry missing version")

    gates = data.get("gates")
    if not isinstance(gates, list):
        errors.append("gates must be a list")
        return set()

    seen: set[str] = set()
    for idx, gate in enumerate(gates):
        if not isinstance(gate, dict):
            errors.append(f"gates[{idx}] must be a mapping")
            continue
        gate_id = str(gate.get("id", "")).strip()
        description = str(gate.get("description", "")).strip()
        command = str(gate.get("command", "")).strip()
        tier = str(gate.get("tier", "")).strip()
        kind = str(gate.get("kind", "")).strip()

        if not gate_id:
            errors.append(f"gates[{idx}] missing id")
        elif not GATE_ID_RE.match(gate_id):
            errors.append(f"gates[{idx}] invalid id: {gate_id}")
        elif gate_id in seen:
            errors.append(f"Duplicate gate id: {gate_id}")
        else:
            seen.add(gate_id)

        if not description:
            errors.append(f"gates[{idx}] missing description")

        if not command:
            errors.append(f"gates[{idx}] missing command")
        else:
            script_path = ROOT / command
            if not script_path.exists():
                errors.append(f"gates[{idx}] command not found: {command}")

        if not tier:
            errors.append(f"gates[{idx}] missing tier")
        elif tier not in ALLOWED_TIERS:
            errors.append(f"gates[{idx}] invalid tier: {tier}")

        if not kind:
            errors.append(f"gates[{idx}] missing kind")
        elif kind not in ALLOWED_KINDS:
            errors.append(f"gates[{idx}] invalid kind: {kind}")

    return seen


def main() -> int:
    errors: list[str] = []
    warnings: list[str] = []

    try:
        registry = _load_yaml(REGISTRY_PATH)
    except (FileNotFoundError, ValueError) as exc:
        print(f"Gate registry check failed: {exc}", file=sys.stderr)
        return 1

    gate_ids = _validate_registry(registry, errors)

    run_all_ids = _extract_run_all_gate_ids()
    missing = sorted(run_all_ids - gate_ids)
    if missing:
        errors.append(f"run-all-gates.sh references unknown gates: {', '.join(missing)}")

    unused = sorted(gate_ids - run_all_ids)
    if unused:
        warnings.append(f"Registry gates not referenced in run-all-gates.sh: {', '.join(unused)}")

    if warnings:
        for warning in warnings:
            print(f"WARNING: {warning}")

    if errors:
        print("Gate registry check failed:", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 1

    print("Gate registry check: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
