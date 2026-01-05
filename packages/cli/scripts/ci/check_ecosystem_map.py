#!/usr/bin/env python3
"""Ensure ecosystem map YAML and website JSON stay in sync and valid."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml


ALLOWED_STATUSES = {"current", "building", "future"}
ALLOWED_ORIGINS = {"internal", "external"}
INTERNAL_STATUSES = {"current", "building", "future"}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _registry_index(registry: dict) -> dict[str, dict]:
    index = {}
    kernel = registry.get("kernel")
    if kernel:
        index[kernel["id"]] = kernel
    for module in registry.get("bundled_modules", []):
        index[module["id"]] = module
    return index


def _proof_ids(ledger: dict) -> set[str]:
    return {claim["id"] for claim in ledger.get("claims", [])}


def _error(msg: str) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)


def _validate_required(node: dict, key: str) -> bool:
    if key not in node or node[key] in (None, ""):
        _error(f"node '{node.get('id', '?')}' missing required field: {key}")
        return False
    return True


def _validate_node(
    node: dict,
    registry: dict[str, dict],
    proof_ids: set[str],
    internal_ids: set[str],
    group_ids: set[str],
    public_root: Path,
) -> bool:
    ok = True
    for key in ("id", "type", "group", "label", "status", "summary", "origin"):
        ok &= _validate_required(node, key)

    if node.get("status") not in ALLOWED_STATUSES:
        _error(f"node '{node.get('id', '?')}' has invalid status: {node.get('status')}")
        ok = False

    if node.get("origin") not in ALLOWED_ORIGINS:
        _error(f"node '{node.get('id', '?')}' has invalid origin: {node.get('origin')}")
        ok = False

    if node.get("group") not in group_ids:
        _error(f"node '{node.get('id', '?')}' has unknown group: {node.get('group')}")
        ok = False

    node_type = node.get("type")
    if node_type not in {"internal", "external"}:
        _error(f"node '{node.get('id', '?')}' has invalid type: {node_type}")
        ok = False
    if node.get("origin") and node_type and node.get("origin") != node_type:
        _error(f"node '{node.get('id', '?')}' origin/type mismatch: {node.get('origin')} vs {node_type}")
        ok = False

    if node_type == "internal":
        if node.get("status") not in INTERNAL_STATUSES:
            _error(f"internal node '{node.get('id', '?')}' must use current/building/future status")
            ok = False
        if not node.get("docs_url"):
            _error(f"internal node '{node.get('id', '?')}' missing docs_url")
            ok = False

        registry_id = node.get("registry_id")
        if registry_id:
            registry_entry = registry.get(registry_id)
            if not registry_entry:
                _error(f"node '{node.get('id', '?')}' registry_id '{registry_id}' not in module registry")
                ok = False
            else:
                if node.get("label") != registry_entry.get("marketing_name"):
                    _error(
                        f"node '{node.get('id', '?')}' label does not match registry marketing_name"
                    )
                    ok = False
                if node.get("summary") != registry_entry.get("description"):
                    _error(
                        f"node '{node.get('id', '?')}' summary does not match registry description"
                    )
                    ok = False
                if node.get("status") != registry_entry.get("status"):
                    _error(
                        f"node '{node.get('id', '?')}' status does not match registry status"
                    )
                    ok = False

    if node_type == "external":
        if not node.get("logo"):
            _error(f"external node '{node.get('id', '?')}' missing logo")
            ok = False
        if not node.get("external_url"):
            _error(f"external node '{node.get('id', '?')}' missing external_url")
            ok = False
        improves = node.get("improves") or []
        if not improves:
            _error(f"external node '{node.get('id', '?')}' missing improves list")
            ok = False
        for entry in improves:
            if not entry.get("label"):
                _error(f"external node '{node.get('id', '?')}' improve entry missing label")
                ok = False
            motus_nodes = entry.get("motus_nodes") or []
            if not motus_nodes:
                _error(f"external node '{node.get('id', '?')}' improve entry missing motus_nodes")
                ok = False
            for motus_node in motus_nodes:
                if motus_node not in internal_ids:
                    _error(
                        f"external node '{node.get('id', '?')}' references unknown motus node '{motus_node}'"
                    )
                    ok = False

    proof_id = node.get("proof_id")
    if proof_id and proof_id not in proof_ids:
        _error(f"node '{node.get('id', '?')}' proof_id '{proof_id}' not in proof ledger")
        ok = False

    logo = node.get("logo")
    if logo:
        if not logo.startswith("/"):
            _error(f"node '{node.get('id', '?')}' logo must be a public path starting with /")
            ok = False
        else:
            path = public_root / logo.lstrip("/")
            if not path.exists():
                _error(f"node '{node.get('id', '?')}' logo missing at {path}")
                ok = False

    return ok


def _validate_group(group: dict, group_ids: set[str]) -> bool:
    ok = True
    for key in ("id", "label", "headline", "description", "relation", "position", "flow_to"):
        ok &= _validate_required(group, key)

    position = group.get("position")
    if not isinstance(position, int):
        _error(f"group '{group.get('id', '?')}' position must be an integer")
        ok = False
    elif position < 1:
        _error(f"group '{group.get('id', '?')}' position must be >= 1")
        ok = False

    flow_to = group.get("flow_to")
    if not isinstance(flow_to, list):
        _error(f"group '{group.get('id', '?')}' flow_to must be a list")
        ok = False
    else:
        for target in flow_to:
            if target not in group_ids:
                _error(f"group '{group.get('id', '?')}' flow_to references unknown group '{target}'")
                ok = False
            if target == group.get("id"):
                _error(f"group '{group.get('id', '?')}' flow_to cannot reference itself")
                ok = False

    return ok


def main() -> int:
    repo_root = _repo_root()
    yaml_path = repo_root / "packages" / "cli" / "docs" / "website" / "ecosystem-map.yaml"
    json_path = repo_root / "packages" / "website" / "src" / "data" / "ecosystem-map.json"
    registry_path = repo_root / "packages" / "cli" / "docs" / "standards" / "module-registry.yaml"
    proof_path = repo_root / "packages" / "cli" / "docs" / "website" / "proof-ledger.yaml"
    public_root = repo_root / "packages" / "website" / "public"

    if not yaml_path.exists():
        _error(f"missing {yaml_path}")
        return 2
    if not json_path.exists():
        _error(f"missing {json_path}")
        return 2
    if not registry_path.exists():
        _error(f"missing {registry_path}")
        return 2
    if not proof_path.exists():
        _error(f"missing {proof_path}")
        return 2

    yaml_data = _load_yaml(yaml_path)
    json_data = _load_json(json_path)

    if yaml_data != json_data:
        _error("ecosystem map mismatch between YAML and JSON")
        return 1

    groups = yaml_data.get("groups", [])
    nodes = yaml_data.get("nodes", [])
    if not groups or not nodes:
        _error("ecosystem map must include groups and nodes")
        return 1

    group_ids = {group["id"] for group in groups if group.get("id")}
    if len(group_ids) != len(groups):
        _error("group ids must be unique")
        return 1

    node_ids = [node.get("id") for node in nodes]
    if len(node_ids) != len(set(node_ids)):
        _error("node ids must be unique")
        return 1

    registry = _registry_index(_load_yaml(registry_path))
    proof_ids = _proof_ids(_load_yaml(proof_path))
    internal_ids = {node["id"] for node in nodes if node.get("type") == "internal"}

    ok = True
    for group in groups:
        ok &= _validate_group(group, group_ids)

    positions = [group.get("position") for group in groups]
    if len(set(positions)) != len(groups):
        _error("group positions must be unique")
        ok = False
    expected = list(range(1, len(groups) + 1))
    if sorted(positions) != expected:
        _error("group positions must be contiguous starting at 1")
        ok = False

    for node in nodes:
        ok &= _validate_node(node, registry, proof_ids, internal_ids, group_ids, public_root)

    if not ok:
        return 1

    print("OK: ecosystem map YAML and JSON are in sync and valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
