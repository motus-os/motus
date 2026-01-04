# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Cache helpers for Capabilities loader file reads."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path


@dataclass
class _CachedText:
    mtime: float
    content: str


_TEXT_CACHE: dict[Path, _CachedText] = {}


def read_text_cached(path: Path) -> str | None:
    """Read text from disk with mtime-based caching."""
    if not path.exists():
        return None

    try:
        mtime = path.stat().st_mtime
    except OSError:
        return None

    cached = _TEXT_CACHE.get(path)
    if cached and cached.mtime == mtime:
        return cached.content

    try:
        content = path.read_text()
    except OSError:
        return None

    _TEXT_CACHE[path] = _CachedText(mtime=mtime, content=content)
    return content


def invalidate_cache(path: Path | None = None) -> None:
    """Invalidate cached reads for a path or clear all cache."""
    if path is None:
        _TEXT_CACHE.clear()
        return

    _TEXT_CACHE.pop(path, None)


def log_gap(base_path: Path | None, path: str, agent_id: str) -> None:
    """Append a gap entry to GAP-LOG.md if missing."""
    if base_path is None:
        return

    gap_log = base_path / "core" / "best-practices" / "GAP-LOG.md"

    if not gap_log.exists():
        return

    content = read_text_cached(gap_log)
    if content and path in content:
        return

    entry = f"| {date.today()} | {agent_id} | {path} | TBD | 1st |\n"
    try:
        with open(gap_log, "a") as f:
            f.write(entry)
        invalidate_cache(gap_log)
    except Exception:
        pass


def get_registry_suggestion(base_path: Path | None, path: str) -> dict | None:
    """Look up suggestion from VARIABLE-REGISTRY.md."""
    if base_path is None:
        return None

    registry_path = base_path / "core" / "dna" / "VARIABLE-REGISTRY.md"

    if not registry_path.exists():
        return None

    content = read_text_cached(registry_path)
    if not content:
        return None

    try:
        pattern = (
            rf"\|\s*`{re.escape(path)}`\s*\|\s*(\w+)\s*\|\s*`?([^|]+?)`?\s*\|\s*([^|]+?)\s*\|"
        )
        match = re.search(pattern, content)

        if match:
            return {
                "type": match.group(1).strip(),
                "default": match.group(2).strip().strip("`"),
                "rationale": match.group(3).strip(),
            }
    except Exception:
        pass

    return None


def detect_product_from_repo(repo_path: Path, yaml_module) -> str | None:
    """Attempt to detect product ID from repository structure."""
    config_paths = [
        repo_path / ".motus.yaml",
        repo_path / ".motus.yml",
        repo_path / "motus.yaml",
    ]

    for cfg_path in config_paths:
        if cfg_path.exists() and yaml_module is not None:
            try:
                with open(cfg_path) as f:
                    data = yaml_module.safe_load(f) or {}
                    if "product" in data:
                        return data["product"]
            except Exception:
                pass

    repo_name = repo_path.name.lower()
    known_products = {
        "project-emmaus": "emmaus",
        "emmaus": "emmaus",
        "motus": "motus",
    }

    return known_products.get(repo_name)


class CapabilitiesHelperMixin:
    """Zero-thinking helper methods for Capabilities accessors."""

    def infer_cr_type(self, title: str) -> str:
        title_lower = title.lower()
        rules = self.cr.get("defaults", {}).get("type_inference", {})
        for keyword, cr_type in rules.items():
            if keyword in title_lower:
                return cr_type
        return "ENHANCEMENT"

    def infer_priority(self, cr_type_or_category: str) -> str:
        rules = self.cr.get("defaults", {}).get("priority_rules", {})
        return rules.get(cr_type_or_category.lower(), "P2")

    def infer_size(self, file_count: int) -> str:
        if file_count <= 1:
            return "S"
        if file_count <= 5:
            return "M"
        return "L"

    def get_gates(self, *categories: str) -> list[str]:
        gates_config = self.cr.get("gates", {})
        result = list(gates_config.get("all", []))
        for cat in categories:
            result.extend(gates_config.get(cat.lower(), []))
        return list(dict.fromkeys(result))

    def get_test_command(self, test_type: str = "unit") -> str:
        return self.test.get(test_type, {}).get("command", "pytest")

    def get_max_lines_per_file(self) -> int:
        return self.code.get("max_lines_per_file", 300)

    def get_warning_lines_per_file(self) -> int:
        return self.code.get("warning_lines_per_file", 500)

    def get_critical_lines_per_file(self) -> int:
        return self.code.get("critical_lines_per_file", 800)

    def get_coverage_threshold(self) -> int:
        return self.test.get("unit", {}).get("coverage_threshold", 80)

    def get_type_coverage_threshold(self) -> int:
        return self.code.get("type_coverage_threshold", 90)

    def get_forbidden_patterns(self) -> list[str]:
        return self.code.get("forbidden_patterns", [])

    def get_verification_tier(self, tier: str) -> dict:
        return self.verification.get("tiers", {}).get(tier, {})

    def get_agent_permissions(self, role: str) -> dict:
        roles = self.agents.get("roles", {})
        return roles.get(role, {"can": [], "cannot": []})

    def is_valid_transition(self, from_status: str, to_status: str) -> bool:
        valid = self.cr.get("status_transitions", {}).get("valid", [])
        return [from_status, to_status] in valid


# Backwards compatibility alias
DNAHelperMixin = CapabilitiesHelperMixin
