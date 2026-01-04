# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Permit tokens for binding policy decisions to side effects.

Motus permits are designed to support "no permit, no run" execution:
- a gate engine issues a signed Permit describing an allowed action
- an execution runtime refuses to run unless a Permit is present and valid

This v0.1 implementation is intentionally dependency-light (stdlib only) and
uses HMAC-SHA256 signatures.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Sequence

SIGNATURE_PREFIX_HMAC_SHA256 = "hmac-sha256:"
PERMIT_VERSION = "0.1.0"


class PermitValidationError(ValueError):
    def __init__(self, reason_code: str, message: str) -> None:
        super().__init__(message)
        self.reason_code = reason_code


def _canonical_json_bytes(data: dict) -> bytes:
    return json.dumps(
        data,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _parse_iso_datetime(value: str) -> datetime | None:
    raw = value.strip()
    if not raw:
        return None
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def compute_permit_hash(permit_dict: dict) -> str:
    """Compute a deterministic sha256 hash for a permit dict.

    Excludes self-referential fields: `permit_hash` and `signature`.
    """
    material = dict(permit_dict)
    material.pop("permit_hash", None)
    material.pop("signature", None)
    return hashlib.sha256(_canonical_json_bytes(material)).hexdigest()


def sign_permit_hash_hmac_sha256(*, permit_hash: str, signing_key: str) -> str:
    digest = hmac.new(
        signing_key.encode("utf-8"),
        permit_hash.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"{SIGNATURE_PREFIX_HMAC_SHA256}{digest}"


def verify_hmac_sha256_signature(*, permit_hash: str, signature: str, signing_key: str) -> bool:
    if not signature.startswith(SIGNATURE_PREFIX_HMAC_SHA256):
        return False
    expected = sign_permit_hash_hmac_sha256(permit_hash=permit_hash, signing_key=signing_key)
    return hmac.compare_digest(expected, signature)


def _normalize_scope_path(value: str) -> str:
    return value.replace("\\", "/").removeprefix("./")


def _normalize_segments(segments: Sequence[Sequence[str]]) -> list[list[str]]:
    return [list(seg) for seg in segments]


@dataclass(frozen=True)
class Permit:
    version: str
    permit_id: str
    run_id: str
    tool_id: str
    plan_hash: str
    issued_at: str
    expires_at: str
    cwd: str
    argv_segments: list[list[str]]
    scope_paths: list[str]
    permit_hash: str | None = None
    signature: str | None = None
    key_id: str | None = None

    def to_dict(self) -> dict:
        result: dict = {
            "version": self.version,
            "permit_id": self.permit_id,
            "run_id": self.run_id,
            "tool_id": self.tool_id,
            "plan_hash": self.plan_hash,
            "issued_at": self.issued_at,
            "expires_at": self.expires_at,
            "cwd": self.cwd,
            "argv_segments": [list(seg) for seg in self.argv_segments],
            "scope_paths": list(self.scope_paths),
        }
        if self.permit_hash is not None:
            result["permit_hash"] = self.permit_hash
        if self.signature is not None:
            result["signature"] = self.signature
        if self.key_id is not None:
            result["key_id"] = self.key_id
        return result

    @classmethod
    def from_dict(cls, data: dict) -> "Permit":
        return cls(
            version=str(data.get("version") or ""),
            permit_id=str(data.get("permit_id") or ""),
            run_id=str(data.get("run_id") or ""),
            tool_id=str(data.get("tool_id") or ""),
            plan_hash=str(data.get("plan_hash") or ""),
            issued_at=str(data.get("issued_at") or ""),
            expires_at=str(data.get("expires_at") or ""),
            cwd=str(data.get("cwd") or ""),
            argv_segments=[list(seg) for seg in (data.get("argv_segments") or [])],
            scope_paths=[str(p) for p in (data.get("scope_paths") or [])],
            permit_hash=str(data.get("permit_hash") or "") or None,
            signature=str(data.get("signature") or "") or None,
            key_id=str(data.get("key_id") or "") or None,
        )


def issue_permit_hmac_sha256(
    *,
    permit_id: str,
    run_id: str,
    tool_id: str,
    plan_hash: str,
    issued_at: str,
    expires_at: str,
    cwd: str,
    argv_segments: Sequence[Sequence[str]],
    scope_paths: Sequence[str],
    signing_key: str,
    key_id: str | None = None,
) -> Permit:
    permit = Permit(
        version=PERMIT_VERSION,
        permit_id=permit_id,
        run_id=run_id,
        tool_id=tool_id,
        plan_hash=plan_hash,
        issued_at=issued_at,
        expires_at=expires_at,
        cwd=cwd,
        argv_segments=_normalize_segments(argv_segments),
        scope_paths=sorted({_normalize_scope_path(p) for p in scope_paths if p}),
        key_id=key_id,
    )
    permit_hash = compute_permit_hash(permit.to_dict())
    signature = sign_permit_hash_hmac_sha256(permit_hash=permit_hash, signing_key=signing_key)
    return Permit.from_dict(
        {**permit.to_dict(), "permit_hash": permit_hash, "signature": signature}
    )


def validate_permit_hmac_sha256(
    permit: Permit | None,
    *,
    expected_run_id: str,
    expected_tool_id: str,
    expected_plan_hash: str,
    expected_cwd: str,
    expected_argv_segments: Sequence[Sequence[str]],
    expected_scope_paths: Sequence[str],
    signing_key: str,
    now: datetime | None = None,
) -> Permit:
    if permit is None:
        raise PermitValidationError("PERMIT.MISSING", "missing permit")

    if permit.version != PERMIT_VERSION:
        raise PermitValidationError(
            "PERMIT.VERSION", f"unsupported permit version: {permit.version!r}"
        )

    if permit.signature is None or not permit.signature.strip():
        raise PermitValidationError("PERMIT.MISSING_SIGNATURE", "missing permit signature")

    computed_hash = compute_permit_hash(permit.to_dict())
    if permit.permit_hash and permit.permit_hash != computed_hash:
        raise PermitValidationError("PERMIT.HASH_MISMATCH", "permit hash mismatch")

    if not verify_hmac_sha256_signature(
        permit_hash=computed_hash, signature=permit.signature, signing_key=signing_key
    ):
        raise PermitValidationError("PERMIT.INVALID_SIGNATURE", "invalid permit signature")

    if permit.run_id != expected_run_id:
        raise PermitValidationError("PERMIT.MISMATCH_RUN_ID", "permit run_id mismatch")

    if permit.tool_id != expected_tool_id:
        raise PermitValidationError("PERMIT.MISMATCH_TOOL", "permit tool_id mismatch")

    if permit.plan_hash != expected_plan_hash:
        raise PermitValidationError("PERMIT.MISMATCH_PLAN", "permit plan_hash mismatch")

    if permit.cwd != expected_cwd:
        raise PermitValidationError("PERMIT.MISMATCH_CWD", "permit cwd mismatch")

    normalized_expected_segments = _normalize_segments(expected_argv_segments)
    if permit.argv_segments != normalized_expected_segments:
        raise PermitValidationError("PERMIT.MISMATCH_ARGS", "permit argv mismatch")

    normalized_expected_scope = sorted(
        {_normalize_scope_path(p) for p in expected_scope_paths if p}
    )
    if permit.scope_paths != normalized_expected_scope:
        raise PermitValidationError("PERMIT.MISMATCH_SCOPE", "permit scope mismatch")

    now_dt = now.astimezone(timezone.utc) if now is not None else datetime.now(timezone.utc)
    expires_at = _parse_iso_datetime(permit.expires_at)
    if expires_at is None:
        raise PermitValidationError("PERMIT.EXPIRES_AT", "invalid expires_at")
    if now_dt > expires_at:
        raise PermitValidationError("PERMIT.EXPIRED", "permit expired")

    return permit
