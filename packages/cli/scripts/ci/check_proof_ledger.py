#!/usr/bin/env python3
"""Ensure proof ledger YAML and website JSON stay in sync."""
from __future__ import annotations

import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import yaml
from jsonschema import Draft7Validator


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _claim_ids(data: dict) -> list[str]:
    return [claim["id"] for claim in data.get("claims", [])]


def _parse_date(value: str) -> date | None:
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _validate_schema(data: dict, schema_path: Path, errors: list[str], label: str) -> None:
    if not schema_path.exists():
        errors.append(f"missing schema: {schema_path}")
        return
    schema = _load_json(schema_path)
    validator = Draft7Validator(schema)
    for err in validator.iter_errors(data):
        errors.append(f"{label}: schema error at {list(err.path)}: {err.message}")


def _validate_current_claims(data: dict, errors: list[str], label: str) -> None:
    today = datetime.now(timezone.utc).date()
    for claim in data.get("claims", []):
        if claim.get("status") != "current":
            continue
        claim_id = claim.get("id", "")
        for field in ("verified_on", "expires_on", "verified_by"):
            if not str(claim.get(field, "")).strip():
                errors.append(f"{label}: claim {claim_id} missing {field}")
        expires_on = str(claim.get("expires_on", "")).strip()
        if expires_on:
            parsed = _parse_date(expires_on)
            if not parsed:
                errors.append(f"{label}: claim {claim_id} has invalid expires_on: {expires_on}")
            elif parsed < today:
                errors.append(f"{label}: claim {claim_id} expired on {expires_on}")


def main() -> int:
    repo_root = _repo_root()
    yaml_path = repo_root / "packages" / "cli" / "docs" / "website" / "proof-ledger.yaml"
    json_path = repo_root / "packages" / "website" / "src" / "data" / "proof-ledger.json"
    schema_path = repo_root / "packages" / "cli" / "docs" / "website" / "proof-ledger.schema.json"

    if not yaml_path.exists():
        print(f"ERROR: missing {yaml_path}", file=sys.stderr)
        return 2
    if not json_path.exists():
        print(f"ERROR: missing {json_path}", file=sys.stderr)
        return 2

    yaml_data = _load_yaml(yaml_path)
    json_data = _load_json(json_path)

    errors: list[str] = []

    _validate_schema(yaml_data, schema_path, errors, "yaml")
    _validate_schema(json_data, schema_path, errors, "json")
    _validate_current_claims(yaml_data, errors, "yaml")
    _validate_current_claims(json_data, errors, "json")

    if yaml_data != json_data:
        yaml_ids = _claim_ids(yaml_data)
        json_ids = _claim_ids(json_data)

        missing_in_json = [claim_id for claim_id in yaml_ids if claim_id not in json_ids]
        missing_in_yaml = [claim_id for claim_id in json_ids if claim_id not in yaml_ids]

        if missing_in_json:
            errors.append(f"missing in JSON: {', '.join(missing_in_json)}")
        if missing_in_yaml:
            errors.append(f"missing in YAML: {', '.join(missing_in_yaml)}")

    if errors:
        print("ERROR: proof ledger validation failed", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 1

    print("OK: proof ledger validated and in sync")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
