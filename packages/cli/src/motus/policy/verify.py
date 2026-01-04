# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Evidence bundle verifier (hashing + signature checks)."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

import jsonschema

from motus.policy.reason_codes import (
    EVIDENCE_ARTIFACT_HASH_MISMATCH,
    EVIDENCE_ARTIFACT_MISSING,
    EVIDENCE_MANIFEST_MISSING,
    EVIDENCE_PATH_TRAVERSAL,
    EVIDENCE_RUN_HASH_MISMATCH,
    EVIDENCE_SCHEMA_INVALID,
    EVIDENCE_SIGNATURE_INVALID,
    EVIDENCE_SIGNATURE_REQUIRED,
    RECON_SNAPSHOT_MISSING,
    RECON_UNTRACKED_DELTA,
)
from motus.policy.verifiability import (
    compute_run_hash,
    sha256_file,
    verify_hmac_sha256_signature,
)


@dataclass(frozen=True)
class VerificationResult:
    ok: bool
    reason_codes: list[str]
    message: str | None = None

    def to_dict(self) -> dict:
        result: dict = {
            "ok": self.ok,
            "reason_codes": list(self.reason_codes),
        }
        if self.message:
            result["message"] = self.message
        return result


def _profile_requires_signature(profile_id: str | None) -> bool:
    return (profile_id or "personal") in {"team", "enterprise", "regulated"}


def _profile_requires_reconciliation(profile_id: str | None) -> bool:
    return (profile_id or "personal") in {"team", "enterprise", "regulated"}


def _schema_path(vault_dir: Path) -> Path:
    return vault_dir / "core" / "best-practices" / "control-plane" / "evidence-manifest.schema.json"


def _resolve_vault_dir(manifest: dict, vault_dir: Path | None) -> Path | None:
    if vault_dir is not None:
        return vault_dir

    env = os.environ.get("MC_VAULT_DIR", "").strip()
    if env:
        return Path(env).expanduser().resolve()

    manifest_vault = str(manifest.get("vault_dir") or "").strip()
    if manifest_vault:
        return Path(manifest_vault).expanduser().resolve()

    return None


def _validate_schema(*, manifest: dict, vault_dir: Path | None) -> list[str]:
    resolved_vault = _resolve_vault_dir(manifest, vault_dir)
    if resolved_vault is None:
        return [EVIDENCE_SCHEMA_INVALID]

    schema_path = _schema_path(resolved_vault)
    if not schema_path.exists():
        return [EVIDENCE_SCHEMA_INVALID]

    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return [EVIDENCE_SCHEMA_INVALID]

    try:
        jsonschema.validate(manifest, schema)
    except jsonschema.ValidationError:
        return [EVIDENCE_SCHEMA_INVALID]

    return []


def verify_evidence_bundle(
    *, evidence_dir: Path, vault_dir: Path | None = None
) -> VerificationResult:
    """Verify an evidence bundle on disk.

    Checks:
    - evidence manifest exists and validates against Vault schema
    - artifact hashes match
    - run hash recomputes deterministically
    - signature verifies when present/required (HMAC-SHA256 v0.1)
    """

    manifest_path = evidence_dir / "manifest.json"
    if not manifest_path.exists():
        return VerificationResult(
            ok=False,
            reason_codes=[EVIDENCE_MANIFEST_MISSING],
            message="Evidence manifest not found",
        )

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return VerificationResult(
            ok=False,
            reason_codes=[EVIDENCE_SCHEMA_INVALID],
            message="Evidence manifest is not valid JSON",
        )

    reason_codes: list[str] = []
    message_parts: list[str] = []

    reason_codes.extend(_validate_schema(manifest=manifest, vault_dir=vault_dir))
    if EVIDENCE_SCHEMA_INVALID in reason_codes:
        message_parts.append("Evidence manifest failed schema validation")

    for entry in manifest.get("artifact_hashes") or []:
        rel = str(entry.get("path") or "").strip()
        expected = str(entry.get("sha256") or "").strip()
        if not rel or not expected:
            continue

        # Security: Prevent path traversal attacks
        # Reject absolute paths and paths that escape evidence_dir
        if Path(rel).is_absolute():
            if EVIDENCE_PATH_TRAVERSAL not in reason_codes:
                reason_codes.append(EVIDENCE_PATH_TRAVERSAL)
            message_parts.append(f"Path traversal rejected (absolute): {rel}")
            continue

        path = Path(os.path.realpath(evidence_dir / rel))
        evidence_dir_resolved = Path(os.path.realpath(evidence_dir))

        # Python 3.9+ is_relative_to check
        try:
            path.relative_to(evidence_dir_resolved)
        except ValueError:
            # Path escapes evidence_dir (e.g., ../../../etc/passwd)
            if EVIDENCE_PATH_TRAVERSAL not in reason_codes:
                reason_codes.append(EVIDENCE_PATH_TRAVERSAL)
            message_parts.append(f"Path traversal rejected (escape): {rel}")
            continue

        if not path.exists():
            if EVIDENCE_ARTIFACT_MISSING not in reason_codes:
                reason_codes.append(EVIDENCE_ARTIFACT_MISSING)
            message_parts.append(f"Missing artifact: {rel}")
            continue
        actual = sha256_file(path)
        if actual != expected:
            if EVIDENCE_ARTIFACT_HASH_MISMATCH not in reason_codes:
                reason_codes.append(EVIDENCE_ARTIFACT_HASH_MISMATCH)
            message_parts.append(f"Artifact hash mismatch: {rel}")

    recorded_run_hash = str(manifest.get("run_hash") or "").strip()
    computed_run_hash = compute_run_hash(manifest)
    if not recorded_run_hash or recorded_run_hash != computed_run_hash:
        reason_codes.append(EVIDENCE_RUN_HASH_MISMATCH)
        message_parts.append("run_hash mismatch")

    profile_id = str(manifest.get("profile_id") or "").strip() or None
    reconciliation_required = _profile_requires_reconciliation(profile_id)

    workspace_delta = manifest.get("workspace_delta_paths", None)
    untracked_delta = manifest.get("untracked_delta_paths", None)
    if reconciliation_required and (workspace_delta is None or untracked_delta is None):
        reason_codes.append(RECON_SNAPSHOT_MISSING)
        message_parts.append("workspace reconciliation missing")
    if isinstance(untracked_delta, list) and untracked_delta:
        reason_codes.append(RECON_UNTRACKED_DELTA)
        message_parts.append(f"untracked_delta_paths={len(untracked_delta)}")

    signature_required = _profile_requires_signature(profile_id)
    signature = str(manifest.get("signature") or "").strip()
    key_id = str(manifest.get("key_id") or "").strip()

    if signature_required and (not signature or not key_id):
        reason_codes.append(EVIDENCE_SIGNATURE_REQUIRED)
        message_parts.append("signature required by profile")
    elif signature:
        signing_key = os.environ.get("MC_EVIDENCE_SIGNING_KEY", "").strip()
        if not signing_key:
            reason_codes.append(EVIDENCE_SIGNATURE_INVALID)
            message_parts.append("signing key not available for signature verification")
        elif not verify_hmac_sha256_signature(
            run_hash=recorded_run_hash or computed_run_hash,
            signature=signature,
            signing_key=signing_key,
        ):
            reason_codes.append(EVIDENCE_SIGNATURE_INVALID)
            message_parts.append("signature invalid")

    ok = not reason_codes
    return VerificationResult(
        ok=ok, reason_codes=reason_codes, message="; ".join(message_parts) or None
    )
