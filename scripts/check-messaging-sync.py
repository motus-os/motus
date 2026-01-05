#!/usr/bin/env python3
"""Validate messaging sync and guardrails."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
MESSAGING_YAML = REPO_ROOT / "packages" / "cli" / "docs" / "website" / "messaging.yaml"
MESSAGING_JSON = REPO_ROOT / "packages" / "website" / "src" / "data" / "messaging.json"
ROOT_README = REPO_ROOT / "README.md"
CLI_README = REPO_ROOT / "packages" / "cli" / "README.md"
DOCS_TESTS = REPO_ROOT / "docs" / "quality" / "messaging-tests.md"

GENERATED_MARKER = "<!-- GENERATED FILE - DO NOT EDIT DIRECTLY -->"
ALLOWED_DEMO_STATUS = {"real", "placeholder", "none"}
ALLOWED_CLAIM_STATUS = {"verified", "target"}


def _load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _has_number(value: str) -> bool:
    return bool(re.search(r"\d", value or ""))


def _check_json_sync() -> tuple[bool, str]:
    yaml_data = _load_yaml(MESSAGING_YAML)
    json_data = _load_json(MESSAGING_JSON)
    if yaml_data != json_data:
        return False, "messaging.json does not match messaging.yaml"
    return True, "JSON matches YAML"


def _check_generated_markers() -> tuple[bool, str]:
    for path in (ROOT_README, CLI_README):
        content = path.read_text(encoding="utf-8")
        if GENERATED_MARKER not in content:
            return False, f"{path} missing generated marker"
    return True, "Generated markers present"


def _check_readme_content() -> tuple[bool, str]:
    yaml_data = _load_yaml(MESSAGING_YAML)
    content = ROOT_README.read_text(encoding="utf-8")
    if yaml_data.get("one_liner") and yaml_data["one_liner"] not in content:
        return False, "README missing one_liner"
    if yaml_data.get("tagline") and yaml_data["tagline"] not in content:
        return False, "README missing tagline"
    return True, "README content matches messaging"


def _check_forbidden_phrases() -> tuple[bool, str]:
    yaml_data = _load_yaml(MESSAGING_YAML)
    forbidden = yaml_data.get("forbidden_phrases", [])
    targets = [ROOT_README, CLI_README]
    for path in targets:
        content = path.read_text(encoding="utf-8").lower()
        for phrase in forbidden:
            if phrase.lower() in content:
                return False, f"Forbidden phrase '{phrase}' found in {path}"

    json_data = _load_json(MESSAGING_JSON)
    json_data.pop("forbidden_phrases", None)
    content = json.dumps(json_data).lower()
    for phrase in forbidden:
        if phrase.lower() in content:
            return False, f"Forbidden phrase '{phrase}' found in {MESSAGING_JSON}"
    return True, "No forbidden phrases"


def _require_claim(block: dict, label: str) -> tuple[bool, str]:
    claim_status = block.get("claim_status")
    proof_id = block.get("proof_id")
    proof_url = block.get("proof_url")
    if claim_status not in ALLOWED_CLAIM_STATUS:
        return False, f"{label} claim_status must be verified or target"
    if not (proof_id or proof_url):
        return False, f"{label} missing proof_id or proof_url"
    return True, ""


def _check_numeric_claims() -> tuple[bool, str]:
    data = _load_yaml(MESSAGING_YAML)
    hero = data.get("hero", {})
    pain = data.get("pain_statement", {})

    if _has_number(data.get("one_liner", "")):
        ok, msg = _require_claim(hero, "hero")
        if not ok:
            return False, "one_liner has numeric claim but hero proof is missing"

    if _has_number(hero.get("headline", "")):
        ok, msg = _require_claim(hero, "hero")
        if not ok:
            return False, msg

    if _has_number(pain.get("short", "")) or _has_number(pain.get("full", "")):
        ok, msg = _require_claim(pain, "pain_statement")
        if not ok:
            return False, msg

    return True, "Numeric claims are provable"


def _check_demo_status() -> tuple[bool, str]:
    data = _load_yaml(MESSAGING_YAML)
    demo = data.get("demo", {})
    status = demo.get("status", "none")
    if status not in ALLOWED_DEMO_STATUS:
        return False, f"demo.status must be one of {sorted(ALLOWED_DEMO_STATUS)}"
    if status == "real":
        asset = demo.get("asset_path")
        if not asset:
            return False, "demo.status=real but asset_path missing"
        if not (REPO_ROOT / asset).exists():
            return False, f"demo asset missing: {asset}"
    return True, "Demo status valid"


def _check_import_scope() -> tuple[bool, str]:
    allowed = {
        REPO_ROOT / "packages" / "website" / "src" / "pages" / "index.astro",
        REPO_ROOT / "packages" / "website" / "src" / "pages" / "get-started.astro",
    }
    pages_dir = REPO_ROOT / "packages" / "website" / "src" / "pages"
    offenders = []
    for path in pages_dir.rglob("*.astro"):
        if "messaging.json" in path.read_text(encoding="utf-8"):
            if path not in allowed:
                offenders.append(str(path))
    if offenders:
        return False, f"messaging.json import not allowed in: {', '.join(offenders)}"
    return True, "Import scope valid"


def _check_tests_recorded() -> tuple[bool, str]:
    if not DOCS_TESTS.exists():
        return False, f"Missing readiness tests file: {DOCS_TESTS}"
    return True, "Readiness tests file exists"


def main() -> int:
    checks = [
        ("JSON sync", _check_json_sync),
        ("Generated markers", _check_generated_markers),
        ("README content", _check_readme_content),
        ("Forbidden phrases", _check_forbidden_phrases),
        ("Numeric claims", _check_numeric_claims),
        ("Demo status", _check_demo_status),
        ("Import scope", _check_import_scope),
        ("Readiness tests", _check_tests_recorded),
    ]

    all_passed = True
    for name, check_fn in checks:
        passed, message = check_fn()
        status = "\u2713" if passed else "\u2717"
        print(f"{status} {name}: {message}")
        if not passed:
            all_passed = False

    if not all_passed:
        print("\n\u274c Messaging sync check failed.")
        print("Run: python scripts/generate-public-surfaces.py")
        return 1

    print("\n\u2713 All messaging sync checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
