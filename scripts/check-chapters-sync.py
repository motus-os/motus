#!/usr/bin/env python3
"""Validate chapters sync and enforce chapter status rules."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
CHAPTERS_YAML = REPO_ROOT / "packages" / "cli" / "docs" / "website" / "chapters.yaml"
CHAPTERS_JSON = REPO_ROOT / "packages" / "website" / "src" / "data" / "chapters.json"
STATUS_YAML = REPO_ROOT / "packages" / "cli" / "docs" / "website" / "status-system.yaml"
MODULE_REGISTRY = REPO_ROOT / "packages" / "website" / "src" / "data" / "module-registry.json"

VISIBILITY_BY_STATUS = {
    "current": {"prominent", "visible"},
    "building": {"visible", "teaser"},
    "future": {"teaser", "hidden"},
}


def _load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _module_statuses() -> dict[str, str]:
    data = _load_json(MODULE_REGISTRY)
    modules = {data["kernel"]["id"]: data["kernel"]["status"]}
    for module in data.get("bundled_modules", []):
        modules[module["id"]] = module["status"]
    return modules


def _allowed_statuses() -> set[str]:
    status_system = _load_yaml(STATUS_YAML)
    constraints = status_system.get("constraints", {})
    chapters_cfg = constraints.get("chapters", {})
    return set(chapters_cfg.get("allowed", []))


def _check_sync() -> tuple[bool, str]:
    yaml_data = _load_yaml(CHAPTERS_YAML)
    json_data = _load_json(CHAPTERS_JSON)
    if yaml_data != json_data:
        return False, "chapters.json does not match chapters.yaml"
    return True, "chapters.json matches chapters.yaml"


def _check_status_and_visibility(chapters: list[dict]) -> tuple[bool, str]:
    allowed = _allowed_statuses()
    for chapter in chapters:
        status = chapter.get("status")
        visibility = chapter.get("visibility")
        if status not in allowed:
            return False, f"Chapter '{chapter.get('id')}' uses invalid status '{status}'"
        allowed_visibility = VISIBILITY_BY_STATUS.get(status, set())
        if visibility not in allowed_visibility:
            return False, (
                f"Chapter '{chapter.get('id')}' visibility '{visibility}' not allowed for status '{status}'"
            )
        if visibility == "hidden" and chapter.get("pages"):
            return False, f"Chapter '{chapter.get('id')}' is hidden but has pages configured"
    return True, "Chapter status + visibility aligned"


def _check_module_dependencies(chapters: list[dict]) -> tuple[bool, str]:
    module_status = _module_statuses()
    for chapter in chapters:
        chapter_status = chapter.get("status")
        for dep in chapter.get("module_dependencies", []):
            if dep not in module_status:
                return False, f"Chapter '{chapter.get('id')}' references unknown module '{dep}'"
            dep_status = module_status[dep]
            if chapter_status == "current" and dep_status != "current":
                return False, f"Chapter '{chapter.get('id')}' is current but module '{dep}' is '{dep_status}'"
            if chapter_status == "building" and dep_status == "future":
                return False, f"Chapter '{chapter.get('id')}' is building but module '{dep}' is future"
    return True, "Chapter module dependencies aligned"


def _check_status_evidence(chapters: list[dict]) -> tuple[bool, str]:
    for chapter in chapters:
        if chapter.get("status") != "current":
            continue
        evidence = chapter.get("status_evidence", [])
        if not evidence:
            return False, f"Chapter '{chapter.get('id')}' is current but has no status_evidence"
        for entry in evidence:
            if entry.get("type") != "test":
                continue
            test_ref = entry.get("test", "")
            test_path = test_ref.split("::", 1)[0]
            if not test_path:
                return False, f"Chapter '{chapter.get('id')}' has invalid test reference"
            if not (REPO_ROOT / test_path).exists():
                return False, f"Chapter '{chapter.get('id')}' test file missing: {test_path}"
    return True, "Chapter evidence references valid tests"


def main() -> int:
    if not CHAPTERS_YAML.exists():
        print(f"Missing chapters.yaml at {CHAPTERS_YAML}")
        return 1
    if not CHAPTERS_JSON.exists():
        print(f"Missing chapters.json at {CHAPTERS_JSON}")
        return 1
    if not STATUS_YAML.exists():
        print(f"Missing status-system.yaml at {STATUS_YAML}")
        return 1
    if not MODULE_REGISTRY.exists():
        print(f"Missing module-registry.json at {MODULE_REGISTRY}")
        return 1

    chapters = _load_yaml(CHAPTERS_YAML).get("chapters", [])

    checks = [
        _check_sync,
        lambda: _check_status_and_visibility(chapters),
        lambda: _check_module_dependencies(chapters),
        lambda: _check_status_evidence(chapters),
    ]

    for check in checks:
        ok, message = check()
        if not ok:
            print(message)
            return 1

    print("Chapters sync and governance checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
