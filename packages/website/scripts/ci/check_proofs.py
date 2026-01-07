#!/usr/bin/env python3
"""Fail CI if website proof references are missing or invalid."""

from __future__ import annotations

import json
import posixpath
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
PAGES = SRC / "pages"
DATA = SRC / "data"
PUBLIC = ROOT / "public"

VALID_PAGE_EXTENSIONS = {".astro", ".md", ".mdx", ".html"}
ALLOWED_STATUSES = {"current", "future", "building"}
SKIP_PREFIXES = (
    "http://",
    "https://",
    "mailto:",
    "tel:",
    "javascript:",
    "data:",
    "//",
)


def _normalize_path(path: str) -> str:
    normalized = posixpath.normpath(path)
    if not normalized.startswith("/"):
        normalized = "/" + normalized
    return normalized


def _page_route(path: Path) -> str:
    rel = path.relative_to(PAGES).with_suffix("")
    parts = rel.parts
    if not parts:
        return "/"
    if parts[-1] == "index":
        route = "/" + "/".join(parts[:-1])
    else:
        route = "/" + "/".join(parts)
    return route if route != "/" else "/"


def _build_routes() -> set[str]:
    routes: set[str] = set()
    for path in PAGES.rglob("*"):
        if path.suffix not in VALID_PAGE_EXTENSIONS:
            continue
        route = _page_route(path)
        if route == "/":
            routes.add("/")
        else:
            route = route.rstrip("/")
            routes.add(route)
            routes.add(route + "/")
    return routes


def _build_public_paths() -> set[str]:
    public_paths: set[str] = set()
    if not PUBLIC.exists():
        return public_paths
    for path in PUBLIC.rglob("*"):
        if path.is_file():
            rel = path.relative_to(PUBLIC).as_posix()
            public_paths.add("/" + rel)
    return public_paths


def _clean_url(url: str) -> str:
    url = url.strip()
    if not url:
        return ""
    for prefix in SKIP_PREFIXES:
        if url.startswith(prefix):
            return ""
    url = url.split("#", 1)[0]
    url = url.split("?", 1)[0]
    return url


def _parse_date(value: str) -> date | None:
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _validate_internal_url(url: str, routes: set[str], public_paths: set[str]) -> bool:
    if not url:
        return True
    if not url.startswith("/"):
        return True
    candidate = _normalize_path(url)
    if candidate in routes or candidate.rstrip("/") in routes:
        return True
    if candidate in public_paths:
        return True
    return False


def _extract_proof_ids(value: Any, file_label: str, found: list[tuple[str, str]]) -> None:
    if isinstance(value, dict):
        for key, val in value.items():
            if key == "proof_id" and isinstance(val, str):
                found.append((file_label, val))
            else:
                _extract_proof_ids(val, file_label, found)
    elif isinstance(value, list):
        for item in value:
            _extract_proof_ids(item, file_label, found)


def main() -> int:
    proof_path = DATA / "proof-ledger.json"
    if not proof_path.exists():
        print("ERROR: proof-ledger.json missing", file=sys.stderr)
        return 2

    routes = _build_routes()
    public_paths = _build_public_paths()

    proof = json.loads(proof_path.read_text(encoding="utf-8"))
    claims = proof.get("claims", [])
    claim_ids: list[str] = []
    errors: list[str] = []

    for claim in claims:
        claim_id = claim.get("id", "").strip()
        if not claim_id:
            errors.append("Proof ledger claim missing id")
            continue
        if claim_id in claim_ids:
            errors.append(f"Duplicate claim id: {claim_id}")
            continue
        claim_ids.append(claim_id)

        status = claim.get("status")
        if status not in ALLOWED_STATUSES:
            errors.append(f"Claim {claim_id} has invalid status: {status}")

        if status == "current":
            if not claim.get("verified_on"):
                errors.append(f"Claim {claim_id} is current but missing verified_on")
            if not claim.get("expires_on"):
                errors.append(f"Claim {claim_id} is current but missing expires_on")
            if not claim.get("verified_by"):
                errors.append(f"Claim {claim_id} is current but missing verified_by")
            expires_on = str(claim.get("expires_on", "")).strip()
            if expires_on:
                parsed = _parse_date(expires_on)
                if not parsed:
                    errors.append(f"Claim {claim_id} has invalid expires_on: {expires_on}")
                elif parsed < datetime.now(timezone.utc).date():
                    errors.append(f"Claim {claim_id} expired on {expires_on}")

        evidence = claim.get("evidence", [])
        if not isinstance(evidence, list) or not evidence:
            errors.append(f"Claim {claim_id} missing evidence list")
            continue

        for item in evidence:
            label = str(item.get("label", "")).strip()
            url = str(item.get("url", "")).strip()
            if not label or not url:
                errors.append(f"Claim {claim_id} has empty evidence entry")
                continue
            internal = _clean_url(url)
            if internal and not _validate_internal_url(internal, routes, public_paths):
                errors.append(f"Claim {claim_id} evidence URL not found: {url}")

    claim_id_set = set(claim_ids)

    proof_refs: list[tuple[str, str]] = []
    for data_file in DATA.glob("*.json"):
        if data_file.name == "proof-ledger.json":
            continue
        data = json.loads(data_file.read_text(encoding="utf-8"))
        _extract_proof_ids(data, data_file.name, proof_refs)

    for file_label, proof_id in proof_refs:
        if not proof_id:
            errors.append(f"{file_label} includes empty proof_id")
            continue
        if proof_id not in claim_id_set:
            errors.append(f"{file_label} references unknown proof_id: {proof_id}")

    if errors:
        print("Proof gate failed:", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 1

    print("Proof gate: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
