#!/usr/bin/env python3
"""Validate gate registry against scripts and release runner."""

from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[4]
REGISTRY_PATH = ROOT / "packages" / "cli" / "docs" / "standards" / "gates.yaml"
GATE_DIR = ROOT / "scripts" / "gates"
RUN_ALL = GATE_DIR / "run-all-gates.sh"

GATE_ID_RE = re.compile(r"GATE-[A-Z]+-[0-9]+")
TIER_ID_RE = re.compile(r"^T[0-9]+$")
ALLOWED_KINDS = {
    "intake",
    "plan",
    "tool",
    "artifact",
    "egress",
    "test",
    "lint",
    "security",
}


def _load_registry() -> dict:
    if not REGISTRY_PATH.exists():
        raise FileNotFoundError(f"Missing gate registry: {REGISTRY_PATH}")
    data = yaml.safe_load(REGISTRY_PATH.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError("Gate registry must be a mapping")
    return data


def _extract_gate_id(path: Path) -> str | None:
    try:
        for line in path.read_text(encoding="utf-8").splitlines()[:8]:
            match = GATE_ID_RE.search(line)
            if match:
                return match.group(0)
    except OSError:
        return None
    return None


def _extract_gate_ids_from_text(path: Path) -> set[str]:
    if not path.exists():
        return set()
    return set(GATE_ID_RE.findall(path.read_text(encoding="utf-8")))


def main() -> int:
    errors: list[str] = []
    warnings: list[str] = []

    try:
        registry = _load_registry()
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1

    version = registry.get("version")
    if not isinstance(version, str) or not version.strip():
        errors.append("Registry version is missing or invalid")

    tiers = registry.get("tiers")
    if not isinstance(tiers, list) or not tiers:
        errors.append("Registry tiers must be a non-empty list")
        tier_ids: set[str] = set()
    else:
        tier_ids = set()
        for idx, tier in enumerate(tiers):
            if not isinstance(tier, dict):
                errors.append(f"tiers[{idx}] must be a mapping")
                continue
            tier_id = str(tier.get("id", "")).strip()
            if not tier_id or not TIER_ID_RE.match(tier_id):
                errors.append(f"tiers[{idx}] has invalid id: {tier_id}")
                continue
            if tier_id in tier_ids:
                errors.append(f"Duplicate tier id: {tier_id}")
            tier_ids.add(tier_id)
            if not str(tier.get("name", "")).strip():
                errors.append(f"tiers[{idx}] missing name")
            if not str(tier.get("description", "")).strip():
                errors.append(f"tiers[{idx}] missing description")

    gates = registry.get("gates")
    if not isinstance(gates, list) or not gates:
        errors.append("Registry gates must be a non-empty list")
        gates = []

    registry_ids: set[str] = set()
    command_paths: dict[str, str] = {}
    for idx, gate in enumerate(gates):
        if not isinstance(gate, dict):
            errors.append(f"gates[{idx}] must be a mapping")
            continue
        gate_id = str(gate.get("id", "")).strip()
        if not gate_id or not GATE_ID_RE.fullmatch(gate_id):
            errors.append(f"gates[{idx}] has invalid id: {gate_id}")
            continue
        if gate_id in registry_ids:
            errors.append(f"Duplicate gate id: {gate_id}")
        registry_ids.add(gate_id)

        tier = str(gate.get("tier", "")).strip()
        if tier not in tier_ids:
            errors.append(f"{gate_id} references unknown tier: {tier}")

        kind = str(gate.get("kind", "")).strip()
        if kind not in ALLOWED_KINDS:
            errors.append(f"{gate_id} has invalid kind: {kind}")

        if not str(gate.get("description", "")).strip():
            errors.append(f"{gate_id} missing description")

        command = str(gate.get("command", "")).strip()
        if command:
            command_paths[gate_id] = command

    script_ids: set[str] = set()
    if GATE_DIR.exists():
        for script in sorted(GATE_DIR.glob("gate-*.sh")):
            gate_id = _extract_gate_id(script)
            if not gate_id:
                errors.append(f"Missing gate id header in {script}")
                continue
            script_ids.add(gate_id)

    run_all_ids = _extract_gate_ids_from_text(RUN_ALL)

    unknown_in_registry = sorted(script_ids - registry_ids)
    if unknown_in_registry:
        errors.append(f"Gate scripts missing from registry: {', '.join(unknown_in_registry)}")

    unknown_run_all = sorted(run_all_ids - registry_ids)
    if unknown_run_all:
        errors.append(f"run-all-gates references unknown gate ids: {', '.join(unknown_run_all)}")

    missing_command_files: list[str] = []
    for gate_id, command in command_paths.items():
        command_path = (ROOT / command).resolve()
        if not command_path.exists():
            missing_command_files.append(f"{gate_id} -> {command}")
    if missing_command_files:
        errors.append(f"Missing gate command scripts: {', '.join(missing_command_files)}")

    registry_not_in_runner = sorted(registry_ids - run_all_ids)
    if registry_not_in_runner:
        warnings.append(
            "Gates not referenced in run-all-gates.sh: " + ", ".join(registry_not_in_runner)
        )

    if warnings:
        for warn in warnings:
            print(f"WARNING: {warn}")

    if errors:
        print("Gate registry check failed:", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 1

    print("Gate registry check: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
