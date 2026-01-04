# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Vault OS policy loader and contracts.

This module is intentionally dependency-light and deterministic.
"""

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
from motus.policy.forensics_boundary import (
    FORENSICS_AUTHORITY,
    FORENSICS_POLICY_ID,
    apply_forensics_boundary,
)
from motus.policy.load import (
    load_gate_registry,
    load_pack_registry,
    load_profile_registry,
    load_vault_policy,
)

__all__ = [
    "GateDefinition",
    "GateRegistry",
    "GateTier",
    "PackDefinition",
    "PackRegistry",
    "Profile",
    "ProfileDefaults",
    "ProfileRegistry",
    "VaultPolicyBundle",
    "load_gate_registry",
    "load_pack_registry",
    "load_profile_registry",
    "load_vault_policy",
    "FORENSICS_AUTHORITY",
    "FORENSICS_POLICY_ID",
    "apply_forensics_boundary",
]
