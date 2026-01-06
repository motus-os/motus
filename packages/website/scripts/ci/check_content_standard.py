#!/usr/bin/env python3
"""Validate website content standards and canonical registries."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
STANDARD = ROOT / "CONTENT-STANDARD.md"
TERMS = ROOT / "standards" / "terminology.json"
LEDGER = ROOT / "standards" / "proof-ledger.json"


def _load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path} invalid JSON: {exc}") from exc


def _ensure_list(obj: dict, key: str, errors: list[str]) -> list[str]:
    value = obj.get(key)
    if not isinstance(value, list):
        errors.append(f"{key} must be a list")
        return []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            errors.append(f"{key} contains non-string or empty values")
            break
    return [str(item).strip() for item in value if isinstance(item, str)]


def _validate_terminology(errors: list[str]) -> None:
    if not TERMS.exists():
        errors.append("standards/terminology.json missing")
        return
    terms = _load_json(TERMS)
    for key in ("approved", "banned_marketing", "requires_definition"):
        _ensure_list(terms, key, errors)


def _validate_ledger(errors: list[str]) -> None:
    if not LEDGER.exists():
        errors.append("standards/proof-ledger.json missing")
        return
    ledger = _load_json(LEDGER)
    required_fields = _ensure_list(ledger, "required_fields", errors)
    status_values = _ensure_list(ledger, "status_values", errors)
    claims = ledger.get("claims")
    if not isinstance(claims, list):
        errors.append("claims must be a list")
        return

    seen_ids: set[str] = set()
    for idx, claim in enumerate(claims):
        if not isinstance(claim, dict):
            errors.append(f"claims[{idx}] must be an object")
            continue
        claim_id = str(claim.get("id", "")).strip()
        if not claim_id:
            errors.append(f"claims[{idx}] missing id")
            continue
        if claim_id in seen_ids:
            errors.append(f"Duplicate claim id: {claim_id}")
        seen_ids.add(claim_id)

        for field in required_fields:
            if field not in claim or str(claim.get(field, "")).strip() == "":
                errors.append(f"Claim {claim_id} missing required field: {field}")

        status = str(claim.get("status", "")).strip()
        if status and status_values and status not in status_values:
            errors.append(f"Claim {claim_id} has invalid status: {status}")

        evidence_path = str(claim.get("evidence_path", "")).strip()
        if evidence_path:
            normalized = evidence_path.lstrip("/")
            candidate = ROOT / normalized
            if not candidate.exists():
                errors.append(f"Claim {claim_id} evidence_path not found: {evidence_path}")


def main() -> int:
    errors: list[str] = []

    if not STANDARD.exists() or STANDARD.stat().st_size == 0:
        errors.append("CONTENT-STANDARD.md missing or empty")

    _validate_terminology(errors)
    _validate_ledger(errors)

    if errors:
        print("Content standard check failed:", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 1

    print("Content standard check: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
