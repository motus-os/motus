# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Dataclass contracts for Vault OS policy artifacts.

These objects are loaded from JSON policy files in a Vault directory.
They are intentionally small and boring.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import List


@dataclass(frozen=True)
class SourceState:
    vcs: str
    commit_sha: str
    dirty: bool
    ref: str | None = None

    def to_dict(self) -> dict:
        result: dict = {"vcs": self.vcs, "commit_sha": self.commit_sha, "dirty": self.dirty}
        if self.ref is not None:
            result["ref"] = self.ref
        return result


@dataclass(frozen=True)
class PackDefinition:
    id: str
    path: str
    precedence: int
    scopes: List[str]
    gate_tier: str
    coverage_tags: List[str]
    version: str
    owner: str
    status: str
    replacement: str


@dataclass(frozen=True)
class PackRegistry:
    version: str
    packs: List[PackDefinition]


@dataclass(frozen=True)
class GateTier:
    id: str
    name: str
    description: str


@dataclass(frozen=True)
class GateDefinition:
    id: str
    tier: str
    kind: str
    description: str


@dataclass(frozen=True)
class GateRegistry:
    version: str
    tiers: List[GateTier]
    gates: List[GateDefinition]


@dataclass(frozen=True)
class ProfileDefaults:
    pack_cap: int
    gate_tier_min: str


@dataclass(frozen=True)
class Profile:
    id: str
    description: str
    defaults: ProfileDefaults


@dataclass(frozen=True)
class ProfileRegistry:
    version: str
    profiles: List[Profile]


@dataclass(frozen=True)
class VaultPolicyBundle:
    vault_dir: Path
    pack_registry: PackRegistry
    gate_registry: GateRegistry
    profile_registry: ProfileRegistry


@dataclass(frozen=True)
class GateResult:
    gate_id: str
    status: str  # pass|fail|skip (matches vault evidence manifest schema)
    exit_code: int
    duration_ms: int
    log_paths: List[str]

    def to_dict(self) -> dict:
        """Convert gate result to a dictionary for JSON serialization."""
        return {
            "gate_id": self.gate_id,
            "status": self.status,
            "exit_code": self.exit_code,
            "duration_ms": self.duration_ms,
            "log_paths": list(self.log_paths),
        }


@dataclass(frozen=True)
class EvidencePlanRef:
    kind: str  # inline|path
    path: str | None = None
    inline: dict | None = None

    def to_dict(self) -> dict:
        """Convert evidence plan reference to a dictionary for JSON serialization."""
        result: dict = {"kind": self.kind}
        if self.path is not None:
            result["path"] = self.path
        if self.inline is not None:
            result["inline"] = self.inline
        return result


@dataclass(frozen=True)
class ArtifactHash:
    path: str
    sha256: str

    def to_dict(self) -> dict:
        """Convert artifact hash entry to a dictionary for JSON serialization."""
        return {"path": self.path, "sha256": self.sha256}


@dataclass(frozen=True)
class EvidenceManifest:
    version: str
    run_id: str
    created_at: str
    repo_dir: str
    policy_versions: dict[str, str]
    plan: EvidencePlanRef
    gate_results: List[GateResult]
    profile_id: str | None = None
    vault_dir: str | None = None
    artifact_hashes: List[ArtifactHash] | None = None
    workspace_root_start: str | None = None
    workspace_root_end: str | None = None
    workspace_delta_paths: List[str] | None = None
    untracked_delta_paths: List[str] | None = None
    source_state: SourceState | None = None
    run_hash: str | None = None
    prev_run_hash: str | None = None
    signature: str | None = None
    key_id: str | None = None
    budgets: dict | None = None

    def to_dict(self) -> dict:
        """Convert evidence manifest to a dictionary for JSON serialization."""
        result: dict = {
            "version": self.version,
            "run_id": self.run_id,
            "created_at": self.created_at,
            "repo_dir": self.repo_dir,
            "policy_versions": dict(self.policy_versions),
            "plan": self.plan.to_dict(),
            "gate_results": [g.to_dict() for g in self.gate_results],
        }
        if self.profile_id is not None:
            result["profile_id"] = self.profile_id
        if self.vault_dir is not None:
            result["vault_dir"] = self.vault_dir
        if self.artifact_hashes is not None:
            result["artifact_hashes"] = [h.to_dict() for h in self.artifact_hashes]
        if self.workspace_root_start is not None:
            result["workspace_root_start"] = self.workspace_root_start
        if self.workspace_root_end is not None:
            result["workspace_root_end"] = self.workspace_root_end
        if self.workspace_delta_paths is not None:
            result["workspace_delta_paths"] = list(self.workspace_delta_paths)
        if self.untracked_delta_paths is not None:
            result["untracked_delta_paths"] = list(self.untracked_delta_paths)
        if self.source_state is not None:
            result["source_state"] = self.source_state.to_dict()
        if self.run_hash is not None:
            result["run_hash"] = self.run_hash
        if self.prev_run_hash is not None:
            result["prev_run_hash"] = self.prev_run_hash
        if self.signature is not None:
            result["signature"] = self.signature
        if self.key_id is not None:
            result["key_id"] = self.key_id
        if self.budgets is not None:
            result["budgets"] = dict(self.budgets)
        return result
