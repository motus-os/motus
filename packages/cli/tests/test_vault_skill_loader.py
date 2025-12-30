from __future__ import annotations

from pathlib import Path

import pytest

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
from motus.policy.loader import compute_gate_plan


def _policy_with(
    *,
    packs: list[PackDefinition],
    profiles: list[Profile],
    gates: list[GateDefinition],
) -> VaultPolicyBundle:
    return VaultPolicyBundle(
        vault_dir=Path("/vault"),
        pack_registry=PackRegistry(version="0.1.0", packs=packs),
        gate_registry=GateRegistry(
            version="0.1.0",
            tiers=[
                GateTier(id="T0", name="Tier 0", description="fast"),
                GateTier(id="T1", name="Tier 1", description="standard"),
                GateTier(id="T2", name="Tier 2", description="high"),
            ],
            gates=gates,
        ),
        profile_registry=ProfileRegistry(version="0.1.0", profiles=profiles),
    )


def _profiles() -> list[Profile]:
    return [
        Profile(
            id="personal",
            description="Personal",
            defaults=ProfileDefaults(pack_cap=8, gate_tier_min="T0"),
        ),
        Profile(
            id="team", description="Team", defaults=ProfileDefaults(pack_cap=3, gate_tier_min="T1")
        ),
    ]


def _gates() -> list[GateDefinition]:
    return [
        GateDefinition(id="GATE-INTAKE-001", tier="T0", kind="intake", description="intake"),
        GateDefinition(id="GATE-PLAN-001", tier="T0", kind="plan", description="plan"),
        GateDefinition(id="GATE-TOOL-001", tier="T1", kind="tool", description="tool"),
        GateDefinition(id="GATE-ARTIFACT-001", tier="T1", kind="artifact", description="artifact"),
        GateDefinition(id="GATE-EGRESS-001", tier="T2", kind="egress", description="egress"),
    ]


def test_single_pack_match_is_deterministic() -> None:
    policy = _policy_with(
        packs=[
            PackDefinition(
                id="PACK-A",
                path="packs/a.md",
                precedence=10,
                scopes=["src/**/*.py"],
                gate_tier="T0",
                coverage_tags=["CDIO:impl", "SSDF:produce"],
                version="0.1.0",
                owner="Example",
                status="active",
                replacement="",
            )
        ],
        profiles=_profiles(),
        gates=_gates(),
    )

    plan1 = compute_gate_plan(changed_files=["src/app.py"], policy=policy, profile_id="personal")
    plan2 = compute_gate_plan(changed_files=["src/app.py"], policy=policy, profile_id="personal")

    assert plan1.to_dict() == plan2.to_dict()
    assert plan1.packs == ["PACK-A"]
    assert plan1.gate_tier == "T0"
    assert plan1.gates == ["GATE-INTAKE-001", "GATE-PLAN-001"]


def test_multiple_pack_ordering_by_precedence() -> None:
    policy = _policy_with(
        packs=[
            PackDefinition(
                id="PACK-LOW",
                path="packs/low.md",
                precedence=10,
                scopes=["**/*.md"],
                gate_tier="T0",
                coverage_tags=["CDIO:design", "SSDF:prepare"],
                version="0.1.0",
                owner="Example",
                status="active",
                replacement="",
            ),
            PackDefinition(
                id="PACK-HIGH",
                path="packs/high.md",
                precedence=20,
                scopes=["src/**/*.py"],
                gate_tier="T1",
                coverage_tags=["CDIO:impl", "SSDF:produce"],
                version="0.2.0",
                owner="Example",
                status="active",
                replacement="",
            ),
        ],
        profiles=_profiles(),
        gates=_gates(),
    )

    plan = compute_gate_plan(
        changed_files=["README.md", "src/app.py"],
        policy=policy,
        profile_id="personal",
    )

    assert plan.packs == ["PACK-HIGH", "PACK-LOW"]
    assert plan.gate_tier == "T1"
    assert plan.gates == [
        "GATE-INTAKE-001",
        "GATE-PLAN-001",
        "GATE-TOOL-001",
        "GATE-ARTIFACT-001",
    ]


def test_pack_cap_failure_fails_closed_with_guidance() -> None:
    policy = _policy_with(
        packs=[
            PackDefinition(
                id="PACK-1",
                path="packs/1.md",
                precedence=10,
                scopes=["**/*"],
                gate_tier="T0",
                coverage_tags=["CDIO:impl", "SSDF:produce"],
                version="0.1.0",
                owner="Example",
                status="active",
                replacement="",
            ),
            PackDefinition(
                id="PACK-2",
                path="packs/2.md",
                precedence=9,
                scopes=["src/**/*.py"],
                gate_tier="T0",
                coverage_tags=["CDIO:impl", "SSDF:produce"],
                version="0.1.0",
                owner="Example",
                status="active",
                replacement="",
            ),
        ],
        profiles=_profiles(),
        gates=_gates(),
    )

    with pytest.raises(ConfigError, match="split into missions"):
        compute_gate_plan(
            changed_files=["src/app.py"],
            policy=policy,
            profile_id="personal",
            pack_cap=1,
        )


def test_gate_tier_computation_raises_to_highest_required() -> None:
    policy = _policy_with(
        packs=[
            PackDefinition(
                id="PACK-T2",
                path="packs/t2.md",
                precedence=100,
                scopes=["src/**/*.py"],
                gate_tier="T2",
                coverage_tags=["CDIO:operate", "SSDF:respond"],
                version="0.1.0",
                owner="Example",
                status="active",
                replacement="",
            )
        ],
        profiles=_profiles(),
        gates=_gates(),
    )

    plan = compute_gate_plan(changed_files=["src/app.py"], policy=policy, profile_id="personal")
    assert plan.gate_tier == "T2"
    assert plan.gates == [
        "GATE-INTAKE-001",
        "GATE-PLAN-001",
        "GATE-TOOL-001",
        "GATE-ARTIFACT-001",
        "GATE-EGRESS-001",
    ]
