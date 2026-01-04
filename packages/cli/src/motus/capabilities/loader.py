# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Capabilities Loader for Motus."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from motus.config import config

from .loader_cache import (
    CapabilitiesHelperMixin,
    detect_product_from_repo,
    get_registry_suggestion,
    log_gap,
)

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore[assignment]


def deep_merge(base: dict, overlay: dict) -> dict:
    """Deep merge two dicts, overlay wins on conflicts."""
    result = base.copy()
    for key, value in overlay.items():
        if key == "extends":
            continue
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def get_nested(d: dict, path: str, default: Any = None) -> Any:
    """Get nested value by dot path."""
    keys = path.split(".")
    for key in keys:
        if isinstance(d, dict) and key in d:
            d = d[key]
        else:
            return default
    return d


@dataclass
class Capabilities(CapabilitiesHelperMixin):
    """Loaded and merged Capabilities configuration."""

    product: dict = field(default_factory=dict)
    design: dict = field(default_factory=dict)
    test: dict = field(default_factory=dict)
    cr: dict = field(default_factory=dict)
    commit: dict = field(default_factory=dict)
    code: dict = field(default_factory=dict)
    paths: dict = field(default_factory=dict)
    patterns: dict = field(default_factory=dict)
    agents: dict = field(default_factory=dict)
    coordination: dict = field(default_factory=dict)
    memos: dict = field(default_factory=dict)
    gap_process: dict = field(default_factory=dict)
    promotion: dict = field(default_factory=dict)
    dora: dict = field(default_factory=dict)
    space: dict = field(default_factory=dict)
    sre: dict = field(default_factory=dict)
    verification: dict = field(default_factory=dict)
    model_selection: dict = field(default_factory=dict)
    security: dict = field(default_factory=dict)
    _raw: dict = field(default_factory=dict)
    _base_path: Path | None = field(default=None, repr=False)

    @classmethod
    def load(cls, product_id: str, base_path: Path | None = None) -> "Capabilities":
        """Load product configuration with inheritance from vault."""
        if yaml is None:
            raise ImportError("PyYAML required: pip install pyyaml")

        if base_path is None:
            base_path = config.paths.vault_dir
            if base_path is None:
                raise ValueError("Vault directory not configured. Set MC_VAULT_DIR.")

        vault_path = base_path / "core" / "capabilities" / "vault.yaml"
        product_path = base_path / "products" / product_id / "dna.yaml"

        if not vault_path.exists():
            raise FileNotFoundError(f"Vault configuration not found: {vault_path}")

        with open(vault_path) as f:
            base = yaml.safe_load(f) or {}

        overlay = {}
        if product_path.exists():
            with open(product_path) as f:
                overlay = yaml.safe_load(f) or {}

        merged = deep_merge(base, overlay)

        return cls(
            product=merged.get("product", {}),
            design=merged.get("design", {}),
            test=merged.get("test", {}),
            cr=merged.get("cr", {}),
            commit=merged.get("commit", {}),
            code=merged.get("code", {}),
            paths=merged.get("paths", {}),
            patterns=merged.get("patterns", {}),
            agents=merged.get("agents", {}),
            coordination=merged.get("coordination", {}),
            memos=merged.get("memos", {}),
            gap_process=merged.get("gap_process", {}),
            promotion=merged.get("promotion", {}),
            dora=merged.get("dora", {}),
            space=merged.get("space", {}),
            sre=merged.get("sre", {}),
            verification=merged.get("verification", {}),
            model_selection=merged.get("model_selection", {}),
            security=merged.get("security", {}),
            _raw=merged,
            _base_path=base_path,
        )

    @classmethod
    def load_base(cls, base_path: Path | None = None) -> "Capabilities":
        """Load just the base vault configuration without product overlay."""
        if yaml is None:
            raise ImportError("PyYAML required: pip install pyyaml")

        if base_path is None:
            base_path = config.paths.vault_dir
            if base_path is None:
                raise ValueError("Vault directory not configured. Set MC_VAULT_DIR.")

        vault_path = base_path / "core" / "capabilities" / "vault.yaml"

        if not vault_path.exists():
            raise FileNotFoundError(f"Vault configuration not found: {vault_path}")

        with open(vault_path) as f:
            data = yaml.safe_load(f) or {}

        return cls(
            product=data.get("product", {}),
            design=data.get("design", {}),
            test=data.get("test", {}),
            cr=data.get("cr", {}),
            commit=data.get("commit", {}),
            code=data.get("code", {}),
            paths=data.get("paths", {}),
            patterns=data.get("patterns", {}),
            agents=data.get("agents", {}),
            coordination=data.get("coordination", {}),
            memos=data.get("memos", {}),
            gap_process=data.get("gap_process", {}),
            promotion=data.get("promotion", {}),
            dora=data.get("dora", {}),
            space=data.get("space", {}),
            sre=data.get("sre", {}),
            verification=data.get("verification", {}),
            model_selection=data.get("model_selection", {}),
            security=data.get("security", {}),
            _raw=data,
            _base_path=base_path,
        )

    @classmethod
    def load_for_repo(cls, repo_path: Path) -> "Capabilities":
        """Load configuration for a repository, detecting product from repo structure."""
        product_id = detect_product_from_repo(repo_path, yaml)

        if product_id:
            try:
                return cls.load(product_id)
            except FileNotFoundError:
                pass

        return cls.load_base()

    def get(self, path: str, default: Any = None) -> Any:
        """Get any value by dot path."""
        return get_nested(self._raw, path, default)

    def get_with_prompt(self, path: str, agent_id: str = "unknown") -> Any:
        """Get value, log gap if missing and suggest from registry."""
        value = get_nested(self._raw, path)

        if value is None:
            log_gap(self._base_path, path, agent_id)
            suggestion = get_registry_suggestion(self._base_path, path)
            if suggestion:
                return suggestion["default"]
            return None

        return value


# Backwards compatibility alias
DNA = Capabilities
