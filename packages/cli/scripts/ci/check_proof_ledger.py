#!/usr/bin/env python3
"""Ensure proof ledger YAML and website JSON stay in sync."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _claim_ids(data: dict) -> list[str]:
    return [claim["id"] for claim in data.get("claims", [])]


def main() -> int:
    repo_root = _repo_root()
    yaml_path = repo_root / "packages" / "cli" / "docs" / "website" / "proof-ledger.yaml"
    json_path = repo_root / "packages" / "website" / "src" / "data" / "proof-ledger.json"

    if not yaml_path.exists():
        print(f"ERROR: missing {yaml_path}", file=sys.stderr)
        return 2
    if not json_path.exists():
        print(f"ERROR: missing {json_path}", file=sys.stderr)
        return 2

    yaml_data = _load_yaml(yaml_path)
    json_data = _load_json(json_path)

    if yaml_data == json_data:
        print("OK: proof ledger YAML and JSON are in sync")
        return 0

    yaml_ids = _claim_ids(yaml_data)
    json_ids = _claim_ids(json_data)

    missing_in_json = [claim_id for claim_id in yaml_ids if claim_id not in json_ids]
    missing_in_yaml = [claim_id for claim_id in json_ids if claim_id not in yaml_ids]

    print("ERROR: proof ledger mismatch", file=sys.stderr)
    if missing_in_json:
        print(f"  - Missing in JSON: {', '.join(missing_in_json)}", file=sys.stderr)
    if missing_in_yaml:
        print(f"  - Missing in YAML: {', '.join(missing_in_yaml)}", file=sys.stderr)

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
