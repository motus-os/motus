# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Evidence bundle writer for Vault OS / Motus OS control plane."""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Iterable

from motus.atomic_io import atomic_write_json
from motus.file_lock import FileLockError, file_lock
from motus.policy._runner_utils import _plan_inline_for_manifest
from motus.policy.contracts import EvidenceManifest, EvidencePlanRef, GateResult
from motus.policy.verifiability import (
    compute_artifact_hashes,
    compute_run_hash,
    find_prev_run_hash,
    sign_run_hash_hmac_sha256,
)


@dataclass(frozen=True)
class EvidencePaths:
    root_dir: Path
    logs_dir: Path
    manifest_path: Path
    summary_path: Path


def get_evidence_paths(evidence_run_dir: Path) -> EvidencePaths:
    """Compute standard evidence directory structure paths."""
    logs_dir = evidence_run_dir / "logs"
    return EvidencePaths(
        root_dir=evidence_run_dir,
        logs_dir=logs_dir,
        manifest_path=evidence_run_dir / "manifest.json",
        summary_path=evidence_run_dir / "summary.md",
    )


def ensure_evidence_dirs(evidence_run_dir: Path) -> EvidencePaths:
    """Create evidence directories if they don't exist and return paths."""
    paths = get_evidence_paths(evidence_run_dir)
    paths.root_dir.mkdir(parents=True, exist_ok=True)
    paths.logs_dir.mkdir(parents=True, exist_ok=True)
    return paths


def _as_rel(path: Path, root: Path) -> str:
    """Convert path to relative POSIX format, falling back to absolute if not relative."""
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def write_manifest(paths: EvidencePaths, manifest: EvidenceManifest) -> None:
    """Write evidence manifest as pretty-printed JSON."""
    try:
        with file_lock(paths.manifest_path, exclusive=True):
            atomic_write_json(paths.manifest_path, manifest.to_dict(), sort_keys=True)
    except FileLockError as e:
        raise RuntimeError(
            f"Failed to acquire manifest lock: {paths.manifest_path}: {e}"
        ) from e


def write_summary(
    paths: EvidencePaths,
    *,
    results: Iterable[GateResult],
    manifest_rel_path: str | None = None,
    workspace_delta_paths: list[str] | None = None,
    untracked_delta_paths: list[str] | None = None,
    reconciliation_note: str | None = None,
) -> None:
    """Write evidence summary as markdown with gate results."""
    manifest_ref = manifest_rel_path or _as_rel(paths.manifest_path, paths.root_dir)

    lines: list[str] = []
    lines.append("# Evidence Summary")
    lines.append("")
    lines.append(f"- Manifest: `{manifest_ref}`")
    lines.append("")
    lines.append("## Workspace Reconciliation")
    if reconciliation_note:
        lines.append(f"- Note: {reconciliation_note}")
    if workspace_delta_paths is None:
        lines.append("- workspace_delta_paths: (not available)")
    else:
        lines.append(f"- workspace_delta_paths: {len(workspace_delta_paths)}")
    if untracked_delta_paths is None:
        lines.append("- untracked_delta_paths: (not available)")
    else:
        lines.append(f"- untracked_delta_paths: {len(untracked_delta_paths)}")
        for path in untracked_delta_paths[:50]:
            lines.append(f"  - `{path}`")
        if len(untracked_delta_paths) > 50:
            lines.append(f"  - ... ({len(untracked_delta_paths) - 50} more)")
    lines.append("")
    lines.append("## Gate Results")
    for r in results:
        status = r.status.upper()
        logs = ", ".join(f"`{p}`" for p in r.log_paths)
        lines.append(
            f"- `{r.gate_id}`: **{status}** (exit={r.exit_code}, {r.duration_ms}ms) {logs}"
        )

    try:
        with file_lock(paths.summary_path, exclusive=True):
            paths.summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    except FileLockError as e:
        raise RuntimeError(
            f"Failed to acquire summary lock: {paths.summary_path}: {e}"
        ) from e


def build_manifest(
    *,
    version: str,
    run_id: str,
    created_at: str,
    repo_dir: Path,
    policy,
    plan,
    results: Iterable[GateResult],
    paths: EvidencePaths,
    evidence_base_dir: Path,
    workspace_delta_paths: list[str] | None,
    untracked_delta_paths: list[str] | None,
    source_state: dict | None,
    signing_key_id: str | None,
    signing_key: str | None,
) -> EvidenceManifest:
    artifact_hashes = compute_artifact_hashes(paths.root_dir, exclude_paths={"manifest.json"})
    prev_run_hash = find_prev_run_hash(
        evidence_base_dir=evidence_base_dir, exclude_run_id=run_id
    )
    key_id_for_manifest = (
        signing_key_id if (signing_key_id is not None and signing_key is not None) else None
    )

    plan_inline = _plan_inline_for_manifest(plan)

    base_manifest = EvidenceManifest(
        version=version,
        run_id=run_id,
        created_at=created_at,
        repo_dir=str(repo_dir),
        vault_dir=str(policy.vault_dir) if getattr(policy, "vault_dir", None) else None,
        profile_id=getattr(plan, "profile_id", None),
        policy_versions=plan.policy_versions.to_dict(),
        plan=EvidencePlanRef(kind="inline", inline=plan_inline),
        gate_results=list(results),
        artifact_hashes=artifact_hashes,
        workspace_delta_paths=workspace_delta_paths,
        untracked_delta_paths=untracked_delta_paths,
        source_state=source_state,
        prev_run_hash=prev_run_hash,
        key_id=key_id_for_manifest,
    )

    run_hash_value = compute_run_hash(base_manifest.to_dict())

    signature_value = None
    if signing_key is not None and signing_key_id is not None:
        signature_value = sign_run_hash_hmac_sha256(
            run_hash=run_hash_value, signing_key=signing_key
        )

    final_manifest = replace(base_manifest, run_hash=run_hash_value, signature=signature_value)
    write_manifest(paths, final_manifest)
    return final_manifest
