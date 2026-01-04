# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Deterministic skill loader and gate plan generation.

This module converts:
  changed files → applicable packs → ordered packs → required gate tier → gates

It is intentionally deterministic and dependency-light.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

from motus.exceptions import ConfigError
from motus.policy.contracts import PackDefinition, VaultPolicyBundle
from motus.policy.globs import matches_any
from motus.policy.load import load_vault_policy

CONTROL_PLANE_VERSION = "1.0.0"
DEFAULT_PROFILE_ID = "personal"
PROFILE_ENV_VAR = "MC_PROFILE"


@dataclass(frozen=True)
class PolicyVersions:
    skill_packs_registry: str
    gates: str

    def to_dict(self) -> dict[str, str]:
        return {"skill_packs_registry": self.skill_packs_registry, "gates": self.gates}


@dataclass(frozen=True)
class PackVersion:
    id: str
    version: str
    owner: str
    status: str
    replacement: str

    def to_dict(self) -> dict[str, str]:
        return {
            "id": self.id,
            "version": self.version,
            "owner": self.owner,
            "status": self.status,
            "replacement": self.replacement,
        }


@dataclass(frozen=True)
class PackCap:
    cap: int
    selected: int
    exceeded: bool

    def to_dict(self) -> dict[str, int | bool]:
        return {"cap": self.cap, "selected": self.selected, "exceeded": self.exceeded}


@dataclass(frozen=True)
class GatePlan:
    version: str
    profile_id: str
    policy_versions: PolicyVersions
    packs: list[str]
    pack_versions: list[PackVersion]
    gate_tier: str
    gates: list[str]
    pack_cap: PackCap

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "profile_id": self.profile_id,
            "policy_versions": self.policy_versions.to_dict(),
            "packs": list(self.packs),
            "pack_versions": [p.to_dict() for p in self.pack_versions],
            "gate_tier": self.gate_tier,
            "gates": list(self.gates),
            "pack_cap": self.pack_cap.to_dict(),
        }


def _tier_rank(tier_id: str) -> int:
    match = re.fullmatch(r"T(\d+)", tier_id.strip())
    if not match:
        raise ConfigError("Invalid gate tier id", details=f"tier_id={tier_id!r}")
    return int(match.group(1))


def _max_tier(tiers: Iterable[str]) -> str:
    tier_list = [t for t in tiers if t is not None]
    if not tier_list:
        raise ConfigError("Cannot compute max tier", details="no tier ids provided")
    return max(tier_list, key=_tier_rank)


def _select_profile_id(profile_id: str | None) -> str:
    if profile_id and profile_id.strip():
        return profile_id.strip()
    env_value = os.environ.get(PROFILE_ENV_VAR, "").strip()
    return env_value or DEFAULT_PROFILE_ID


def _select_packs_by_scope(
    packs: Sequence[PackDefinition], changed_files: Sequence[str]
) -> list[PackDefinition]:
    selected: list[PackDefinition] = []
    for pack in packs:
        if any(matches_any(pack.scopes, file_path) for file_path in changed_files):
            selected.append(pack)
    return selected


def _order_packs_by_precedence(packs: Sequence[PackDefinition]) -> list[PackDefinition]:
    return sorted(packs, key=lambda p: (-p.precedence, p.id))


def compute_gate_plan(
    *,
    changed_files: Sequence[str],
    policy: VaultPolicyBundle,
    profile_id: str | None = None,
    pack_cap: int | None = None,
) -> GatePlan:
    """Compute a deterministic GatePlan from changed files and vault policy."""

    resolved_profile_id = _select_profile_id(profile_id)
    profile = next(
        (p for p in policy.profile_registry.profiles if p.id == resolved_profile_id), None
    )
    if profile is None:
        known = ", ".join(sorted(p.id for p in policy.profile_registry.profiles))
        raise ConfigError(
            "Unknown profile id",
            details=f"profile_id={resolved_profile_id!r} (known: {known})",
        )

    applicable = _select_packs_by_scope(policy.pack_registry.packs, list(changed_files))
    ordered_packs = _order_packs_by_precedence(applicable)

    cap_value = pack_cap if pack_cap is not None else profile.defaults.pack_cap
    selected_count = len(ordered_packs)
    exceeded = selected_count > cap_value
    pack_cap_eval = PackCap(cap=cap_value, selected=selected_count, exceeded=exceeded)
    if exceeded:
        pack_ids = ", ".join(p.id for p in ordered_packs)
        raise ConfigError(
            "Pack cap exceeded (split into missions)",
            details=f"selected={selected_count} cap={cap_value} packs=[{pack_ids}]",
        )

    gate_tier = _max_tier([profile.defaults.gate_tier_min] + [p.gate_tier for p in ordered_packs])
    max_rank = _tier_rank(gate_tier)

    gate_ids: list[str] = []
    seen: set[str] = set()
    for gate in policy.gate_registry.gates:
        if _tier_rank(gate.tier) <= max_rank and gate.id not in seen:
            gate_ids.append(gate.id)
            seen.add(gate.id)

    pack_versions = [
        PackVersion(
            id=p.id,
            version=p.version,
            owner=p.owner,
            status=p.status,
            replacement=p.replacement,
        )
        for p in ordered_packs
    ]

    return GatePlan(
        version=CONTROL_PLANE_VERSION,
        profile_id=resolved_profile_id,
        policy_versions=PolicyVersions(
            skill_packs_registry=policy.pack_registry.version,
            gates=policy.gate_registry.version,
        ),
        packs=[p.id for p in ordered_packs],
        pack_versions=pack_versions,
        gate_tier=gate_tier,
        gates=gate_ids,
        pack_cap=pack_cap_eval,
    )


def load_and_compute_gate_plan(
    *,
    changed_files: Sequence[str],
    vault_dir: Path | None = None,
    profile_id: str | None = None,
    pack_cap: int | None = None,
) -> GatePlan:
    """Convenience wrapper that loads vault policy and computes the plan."""

    policy = load_vault_policy(vault_dir)
    return compute_gate_plan(
        changed_files=changed_files,
        policy=policy,
        profile_id=profile_id,
        pack_cap=pack_cap,
    )


def format_gate_plan(plan: GatePlan) -> str:
    """Format a GatePlan for humans (CLI/UI)."""

    lines: list[str] = []
    lines.append(f"profile_id: {plan.profile_id}")
    lines.append(
        "policy_versions:"
        f" skill_packs_registry={plan.policy_versions.skill_packs_registry}"
        f" gates={plan.policy_versions.gates}"
    )
    lines.append(
        f"pack_cap: {plan.pack_cap.selected}/{plan.pack_cap.cap}"
        + (" (exceeded)" if plan.pack_cap.exceeded else "")
    )
    lines.append(f"gate_tier: {plan.gate_tier}")
    lines.append("packs:")
    for pack in plan.pack_versions:
        lines.append(f"  - {pack.id} v{pack.version} ({pack.status}) owner={pack.owner}")
    lines.append("gates:")
    for gate_id in plan.gates:
        lines.append(f"  - {gate_id}")
    return "\n".join(lines)
