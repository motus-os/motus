# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Load and validate Vault OS policy artifacts from a vault directory."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, List, Mapping

from motus.config import config
from motus.exceptions import ConfigError
from motus.policy.contracts import (
    GateDefinition,
    GateRegistry,
    GateTier,
    PackDefinition,
    PackRegistry,
    Profile,
    ProfileDefaults,
    ProfileRegistry,
    VaultPolicyBundle,
)

SUPPORTED_POLICY_VERSIONS = {"0.1.0"}

_PACK_REGISTRY_REL = Path("core/best-practices/skill-packs/registry.json")
_GATES_REL = Path("core/best-practices/gates.json")
_PROFILES_REL = Path("core/best-practices/profiles/profiles.json")


def _read_json(path: Path) -> Any:
    """Read and parse JSON file with descriptive error messages."""
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError as e:
        raise ConfigError("Vault policy file missing", details=str(path)) from e
    except json.JSONDecodeError as e:
        raise ConfigError(
            "Vault policy file is not valid JSON",
            details=f"{path}: {e.msg} (line {e.lineno}, col {e.colno})",
        ) from e


def _require_mapping(value: Any, *, ctx: str) -> Mapping[str, Any]:
    """Validate that value is a mapping (object), raising ConfigError otherwise."""
    if isinstance(value, Mapping):
        return value
    raise ConfigError("Invalid vault policy shape", details=f"{ctx}: expected object")


def _require_list(value: Any, *, ctx: str) -> List[Any]:
    """Validate that value is a list (array), raising ConfigError otherwise."""
    if isinstance(value, list):
        return value
    raise ConfigError("Invalid vault policy shape", details=f"{ctx}: expected array")


def _require_str(value: Any, *, ctx: str) -> str:
    """Validate that value is a string, raising ConfigError otherwise."""
    if isinstance(value, str):
        return value
    raise ConfigError("Invalid vault policy shape", details=f"{ctx}: expected string")


def _require_int(value: Any, *, ctx: str) -> int:
    """Validate that value is an integer, raising ConfigError otherwise."""
    if isinstance(value, int):
        return value
    raise ConfigError("Invalid vault policy shape", details=f"{ctx}: expected integer")


def _check_version(version: str, *, ctx: str) -> None:
    """Validate that policy version is supported, raising ConfigError otherwise."""
    if version not in SUPPORTED_POLICY_VERSIONS:
        supported = ", ".join(sorted(SUPPORTED_POLICY_VERSIONS))
        raise ConfigError(
            "Unsupported vault policy version",
            details=f"{ctx}: {version} (supported: {supported})",
        )


def _resolve_vault_dir(vault_dir: Path | None) -> Path:
    """Resolve vault directory from argument or config, raising ConfigError if missing."""
    resolved = vault_dir or config.paths.vault_dir
    if resolved is None:
        raise ConfigError(
            "Vault directory not configured",
            details="Set MC_VAULT_DIR to your vault root (e.g. /path/to/vault).",
        )
    return resolved


def load_pack_registry(vault_dir: Path | None = None) -> PackRegistry:
    """Load PackRegistry from `<vault>/core/best-practices/skill-packs/registry.json`."""

    root = _resolve_vault_dir(vault_dir)
    path = root / _PACK_REGISTRY_REL
    data = _require_mapping(_read_json(path), ctx=str(path))
    version = _require_str(data.get("version"), ctx=f"{path}:version")
    _check_version(version, ctx=str(path))

    packs_raw = _require_list(data.get("packs"), ctx=f"{path}:packs")
    packs: List[PackDefinition] = []
    for idx, item in enumerate(packs_raw):
        obj = _require_mapping(item, ctx=f"{path}:packs[{idx}]")
        status = _require_str(obj.get("status"), ctx=f"{path}:packs[{idx}].status")
        replacement = _require_str(obj.get("replacement"), ctx=f"{path}:packs[{idx}].replacement")
        if status == "deprecated" and not replacement.strip():
            raise ConfigError(
                "Invalid pack lifecycle metadata",
                details=f"{path}:packs[{idx}] deprecated packs require non-empty replacement",
            )

        packs.append(
            PackDefinition(
                id=_require_str(obj.get("id"), ctx=f"{path}:packs[{idx}].id"),
                path=_require_str(obj.get("path"), ctx=f"{path}:packs[{idx}].path"),
                precedence=_require_int(
                    obj.get("precedence"), ctx=f"{path}:packs[{idx}].precedence"
                ),
                scopes=[
                    _require_str(s, ctx=f"{path}:packs[{idx}].scopes[]")
                    for s in _require_list(obj.get("scopes"), ctx=f"{path}:packs[{idx}].scopes")
                ],
                gate_tier=_require_str(obj.get("gate_tier"), ctx=f"{path}:packs[{idx}].gate_tier"),
                coverage_tags=[
                    _require_str(c, ctx=f"{path}:packs[{idx}].coverage_tags[]")
                    for c in _require_list(
                        obj.get("coverage_tags"), ctx=f"{path}:packs[{idx}].coverage_tags"
                    )
                ],
                version=_require_str(obj.get("version"), ctx=f"{path}:packs[{idx}].version"),
                owner=_require_str(obj.get("owner"), ctx=f"{path}:packs[{idx}].owner"),
                status=status,
                replacement=replacement,
            )
        )

    return PackRegistry(version=version, packs=packs)


def load_gate_registry(vault_dir: Path | None = None) -> GateRegistry:
    """Load GateRegistry from `<vault>/core/best-practices/gates.json`."""

    root = _resolve_vault_dir(vault_dir)
    path = root / _GATES_REL
    data = _require_mapping(_read_json(path), ctx=str(path))
    version = _require_str(data.get("version"), ctx=f"{path}:version")
    _check_version(version, ctx=str(path))

    tiers_raw = _require_list(data.get("tiers"), ctx=f"{path}:tiers")
    tiers: List[GateTier] = []
    for idx, item in enumerate(tiers_raw):
        obj = _require_mapping(item, ctx=f"{path}:tiers[{idx}]")
        tiers.append(
            GateTier(
                id=_require_str(obj.get("id"), ctx=f"{path}:tiers[{idx}].id"),
                name=_require_str(obj.get("name"), ctx=f"{path}:tiers[{idx}].name"),
                description=_require_str(
                    obj.get("description"), ctx=f"{path}:tiers[{idx}].description"
                ),
            )
        )

    gates_raw = _require_list(data.get("gates"), ctx=f"{path}:gates")
    gates: List[GateDefinition] = []
    for idx, item in enumerate(gates_raw):
        obj = _require_mapping(item, ctx=f"{path}:gates[{idx}]")
        gates.append(
            GateDefinition(
                id=_require_str(obj.get("id"), ctx=f"{path}:gates[{idx}].id"),
                tier=_require_str(obj.get("tier"), ctx=f"{path}:gates[{idx}].tier"),
                kind=_require_str(obj.get("kind"), ctx=f"{path}:gates[{idx}].kind"),
                description=_require_str(
                    obj.get("description"), ctx=f"{path}:gates[{idx}].description"
                ),
            )
        )

    return GateRegistry(version=version, tiers=tiers, gates=gates)


def load_profile_registry(vault_dir: Path | None = None) -> ProfileRegistry:
    """Load ProfileRegistry from `<vault>/core/best-practices/profiles/profiles.json`."""

    root = _resolve_vault_dir(vault_dir)
    path = root / _PROFILES_REL
    data = _require_mapping(_read_json(path), ctx=str(path))
    version = _require_str(data.get("version"), ctx=f"{path}:version")
    _check_version(version, ctx=str(path))

    profiles_raw = _require_list(data.get("profiles"), ctx=f"{path}:profiles")
    profiles: List[Profile] = []
    for idx, item in enumerate(profiles_raw):
        obj = _require_mapping(item, ctx=f"{path}:profiles[{idx}]")
        defaults_obj = _require_mapping(obj.get("defaults"), ctx=f"{path}:profiles[{idx}].defaults")
        pack_cap = _require_int(
            defaults_obj.get("pack_cap"), ctx=f"{path}:profiles[{idx}].defaults.pack_cap"
        )
        gate_tier_min = _require_str(
            defaults_obj.get("gate_tier_min"),
            ctx=f"{path}:profiles[{idx}].defaults.gate_tier_min",
        )
        profiles.append(
            Profile(
                id=_require_str(obj.get("id"), ctx=f"{path}:profiles[{idx}].id"),
                description=_require_str(
                    obj.get("description"), ctx=f"{path}:profiles[{idx}].description"
                ),
                defaults=ProfileDefaults(pack_cap=pack_cap, gate_tier_min=gate_tier_min),
            )
        )

    return ProfileRegistry(version=version, profiles=profiles)


def load_vault_policy(vault_dir: Path | None = None) -> VaultPolicyBundle:
    """Load all vault policy artifacts (packs, gates, profiles) from a vault root."""

    root = _resolve_vault_dir(vault_dir)
    return VaultPolicyBundle(
        vault_dir=root,
        pack_registry=load_pack_registry(root),
        gate_registry=load_gate_registry(root),
        profile_registry=load_profile_registry(root),
    )
