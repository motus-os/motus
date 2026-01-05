#!/usr/bin/env python3
"""Validate chapters.yaml sync and enforce chapter status rules."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
CHAPTERS_YAML = REPO_ROOT / "packages" / "cli" / "docs" / "website" / "chapters.yaml"
CHAPTERS_JSON = REPO_ROOT / "packages" / "website" / "src" / "data" / "chapters.json"
STATUS_YAML = REPO_ROOT / "packages" / "cli" / "docs" / "website" / "status-system.yaml"
MODULE_REGISTRY_YAML = REPO_ROOT / "packages" / "cli" / "docs" / "standards" / "module-registry.yaml"

ALLOWED_VISIBILITY = {"prominent", "visible", "teaser", "hidden"}
ALLOWED_PAGES = {"homepage", "how-it-works", "get-started", "implementation", "docs"}

STATUS_RANK = {"future": 0, "building": 1, "current": 2}


def _load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _extract_modules(registry: dict) -> dict[str, str]:
    modules: dict[str, str] = {}
    kernel = registry.get("kernel", {})
    if kernel:
        modules[kernel.get("id", "kernel")] = kernel.get("status", "unknown")
    for module in registry.get("bundled_modules", []) or []:
        module_id = module.get("id")
        if module_id:
            modules[module_id] = module.get("status", "unknown")
    return modules


def _status_allows(chapter_status: str, module_status: str) -> bool:
    return STATUS_RANK.get(module_status, -1) >= STATUS_RANK.get(chapter_status, -1)


def _allowed_chapter_statuses(status_system: dict) -> set[str]:
    constraints = status_system.get("constraints", {})
    chapters = constraints.get("chapters", {})
    return set(chapters.get("allowed", []))


def _check_sync() -> tuple[bool, str]:
    yaml_data = _load_yaml(CHAPTERS_YAML)
    json_data = _load_json(CHAPTERS_JSON)
    if yaml_data != json_data:
        return False, "chapters.json does not match chapters.yaml"
    return True, "JSON matches YAML"


def _check_chapters() -> tuple[bool, str]:
    chapters = _load_yaml(CHAPTERS_YAML).get("chapters", [])
    status_system = _load_yaml(STATUS_YAML)
    registry = _load_yaml(MODULE_REGISTRY_YAML)
    modules = _extract_modules(registry)

    allowed_statuses = _allowed_chapter_statuses(status_system)
    if not allowed_statuses:
        return False, "status-system.yaml missing chapters constraints"

    ids: set[str] = set()
    numbers: set[int] = set()

    for chapter in chapters:
        chapter_id = chapter.get("id")
        number = chapter.get("number")
        status = chapter.get("status")
        visibility = chapter.get("visibility")
        pages = chapter.get("pages", [])

        if not chapter_id:
            return False, "Chapter missing id"
        if chapter_id in ids:
            return False, f"Duplicate chapter id: {chapter_id}"
        ids.add(chapter_id)

        if not isinstance(number, int):
            return False, f"Chapter {chapter_id} missing numeric order"
        if number in numbers:
            return False, f"Duplicate chapter number: {number}"
        numbers.add(number)

        if status not in allowed_statuses:
            return False, f"Chapter {chapter_id} uses invalid status: {status}"

        if visibility not in ALLOWED_VISIBILITY:
            return False, f"Chapter {chapter_id} uses invalid visibility: {visibility}"

        if status == "current" and visibility not in {"prominent", "visible"}:
            return False, f"Chapter {chapter_id} current but visibility is {visibility}"
        if status == "building" and visibility not in {"visible", "teaser"}:
            return False, f"Chapter {chapter_id} building but visibility is {visibility}"
        if status == "future" and visibility not in {"teaser", "hidden"}:
            return False, f"Chapter {chapter_id} future but visibility is {visibility}"

        if pages:
            for page in pages:
                if page not in ALLOWED_PAGES:
                    return False, f"Chapter {chapter_id} references unknown page: {page}"
            if status == "future" and pages:
                return False, f"Chapter {chapter_id} is future but lists pages"

        dependencies = chapter.get("module_dependencies", []) or []
        if not isinstance(dependencies, list):
            return False, f"Chapter {chapter_id} module_dependencies must be list"
        for dep in dependencies:
            if dep not in modules:
                return False, f"Chapter {chapter_id} references unknown module: {dep}"
            if not _status_allows(status, modules[dep]):
                return False, f"Chapter {chapter_id} status {status} exceeds module {dep} status {modules[dep]}"

        if status == "current":
            evidence = chapter.get("status_evidence", [])
            if not evidence:
                return False, f"Chapter {chapter_id} current but missing status_evidence"
            for item in evidence:
                if not item.get("type"):
                    return False, f"Chapter {chapter_id} evidence missing type"
                if item.get("type") in {"test", "cli_command", "integration_test"} and not item.get("test"):
                    return False, f"Chapter {chapter_id} evidence missing test reference"

    return True, "Chapter status and visibility rules are valid"


def main() -> int:
    if not CHAPTERS_YAML.exists():
        print(f"Missing chapters.yaml at {CHAPTERS_YAML}", file=sys.stderr)
        return 2
    if not CHAPTERS_JSON.exists():
        print(f"Missing chapters.json at {CHAPTERS_JSON}", file=sys.stderr)
        return 2

    checks = [
        ("Chapters JSON sync", _check_sync),
        ("Chapter rules", _check_chapters),
    ]

    ok = True
    for name, check in checks:
        passed, msg = check()
        status = "\u2713" if passed else "\u2717"
        print(f"{status} {name}: {msg}")
        ok = ok and passed

    if not ok:
        print("\n\u274c Chapters sync check failed.")
        return 1
    print("\n\u2713 Chapters sync checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
