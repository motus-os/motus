#!/usr/bin/env python3
"""
Conformance Vector Validator

CORE-CONF-002: "Repo must validate itself."

This validator is intentionally **fail-closed**:
- The suite source-of-truth is `conformance/index.json`.
- Every referenced vector must declare an `oracle_ref`.
- The referenced oracle MUST deterministically reproduce the expected outcome and derived fields.

Run: python3 conformance/validate.py
Exit 0 = all vectors match expected outcomes
Exit 1 = one or more failures
"""

from __future__ import annotations

import hashlib
import json
import sys
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

PASS = "PASS"

CONFVEC_ORACLE_MISSING = "CONFVEC.ORACLE_MISSING"
CONFVEC_ORACLE_UNKNOWN = "CONFVEC.ORACLE_UNKNOWN"
CONFVEC_ORACLE_NONDETERMINISTIC = "CONFVEC.ORACLE_NONDETERMINISTIC"
CONFVEC_VECTOR_INVALID = "CONFVEC.VECTOR_INVALID"
CONFVEC_DERIVED_MISMATCH = "CONFVEC.DERIVED_MISMATCH"
CONFVEC_OUTCOME_MISMATCH = "CONFVEC.OUTCOME_MISMATCH"


@dataclass(frozen=True)
class OracleResult:
    outcome: str
    derived: dict[str, Any] | None = None


def _canonical_json(obj: dict) -> str:
    return json.dumps(
        obj,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def _sha256_hex(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def _parse_iso_datetime(value: str) -> datetime | None:
    raw = value.strip()
    if not raw:
        return None
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return None


def _parse_oracle_ref(value: str) -> tuple[str, str, str]:
    """Return (spec_id, version, oracle_name)."""
    spec_and_version, _, oracle_name = value.partition("#")
    spec_id, _, version = spec_and_version.partition("@")
    return (spec_id.strip(), version.strip(), oracle_name.strip())


def _oracle_canonicalization(vector: dict) -> OracleResult:
    if not isinstance(vector.get("input"), dict):
        return OracleResult(CONFVEC_VECTOR_INVALID)

    expected_canonical = vector.get("expected_canonical")
    expected_hash = vector.get("expected_hash")
    if not isinstance(expected_canonical, str) or not isinstance(expected_hash, str):
        return OracleResult(CONFVEC_VECTOR_INVALID)

    computed_canonical = _canonical_json(vector["input"])
    computed_hash = _sha256_hex(computed_canonical)

    derived = {"computed_canonical": computed_canonical, "computed_hash": computed_hash}

    if computed_canonical != expected_canonical or computed_hash != expected_hash:
        return OracleResult(CONFVEC_DERIVED_MISMATCH, derived=derived)

    return OracleResult(PASS, derived=derived)


def _oracle_gate_contract(vector: dict) -> OracleResult:
    input_obj = vector.get("input")
    if not isinstance(input_obj, dict):
        return OracleResult(CONFVEC_VECTOR_INVALID)

    gate = input_obj.get("gate")
    execution = input_obj.get("execution")
    if not isinstance(gate, dict) or not isinstance(execution, dict):
        return OracleResult(CONFVEC_VECTOR_INVALID)

    timeout_ms = gate.get("timeout_ms")
    duration_ms = execution.get("duration_ms")
    exit_code = execution.get("exit_code")
    if not isinstance(timeout_ms, int) or not isinstance(duration_ms, int) or not isinstance(exit_code, int):
        return OracleResult(CONFVEC_VECTOR_INVALID)

    if duration_ms > timeout_ms:
        return OracleResult("FAIL.GATE_TIMEOUT", derived={"duration_ms": duration_ms, "timeout_ms": timeout_ms})
    if exit_code != 0:
        return OracleResult("FAIL.GATE_FAILED", derived={"exit_code": exit_code})
    return OracleResult(PASS)


def _oracle_reconciliation(vector: dict) -> OracleResult:
    input_obj = vector.get("input")
    if not isinstance(input_obj, dict):
        return OracleResult(CONFVEC_VECTOR_INVALID)

    requested = input_obj.get("requested_scope")
    actual = input_obj.get("actual_delta")
    if not isinstance(requested, list) or not isinstance(actual, list):
        return OracleResult(CONFVEC_VECTOR_INVALID)
    if not all(isinstance(p, str) for p in requested) or not all(isinstance(p, str) for p in actual):
        return OracleResult(CONFVEC_VECTOR_INVALID)

    untracked = [p for p in actual if p not in set(requested)]
    computed_result = {"untracked_delta": untracked, "outcome": "FAIL" if untracked else "PASS"}

    expected_result = vector.get("expected_result")
    if expected_result is not None and expected_result != computed_result:
        return OracleResult(CONFVEC_DERIVED_MISMATCH, derived={"computed_result": computed_result})

    if untracked:
        return OracleResult("RECON.UNTRACKED_DELTA", derived={"computed_result": computed_result})
    return OracleResult(PASS, derived={"computed_result": computed_result})


def _oracle_permit(vector: dict) -> OracleResult:
    input_obj = vector.get("input")
    if not isinstance(input_obj, dict):
        return OracleResult(CONFVEC_VECTOR_INVALID)

    permit = input_obj.get("permit")
    if permit is None:
        profile = input_obj.get("profile") or {}
        require_permits = bool(profile.get("require_permits", False))
        if require_permits:
            return OracleResult("FAIL.PERMIT_MISSING")
        return OracleResult(PASS)

    if not isinstance(permit, dict):
        return OracleResult(CONFVEC_VECTOR_INVALID)

    plan_hash = permit.get("plan_hash")
    current_plan_hash = input_obj.get("current_plan_hash")
    if not isinstance(plan_hash, str) or not isinstance(current_plan_hash, str):
        return OracleResult(CONFVEC_VECTOR_INVALID)
    if plan_hash != current_plan_hash:
        return OracleResult("FAIL.PERMIT_HASH_MISMATCH")

    expires_at = permit.get("expires_at")
    current_time = input_obj.get("current_time")
    if isinstance(expires_at, str) and isinstance(current_time, str):
        expires_dt = _parse_iso_datetime(expires_at)
        now_dt = _parse_iso_datetime(current_time)
        if expires_dt is None or now_dt is None:
            return OracleResult(CONFVEC_VECTOR_INVALID)
        if now_dt > expires_dt:
            return OracleResult("FAIL.PERMIT_EXPIRED")

    return OracleResult(PASS)


def _oracle_evidence_bundle(vector: dict) -> OracleResult:
    input_obj = vector.get("input")
    if not isinstance(input_obj, dict):
        return OracleResult(CONFVEC_VECTOR_INVALID)

    manifest = input_obj.get("manifest")
    if not isinstance(manifest, dict):
        return OracleResult(CONFVEC_VECTOR_INVALID)

    required = ["version", "run_id", "created_at", "repo_dir", "policy_versions", "plan", "gate_results"]
    if any(k not in manifest for k in required):
        return OracleResult("FAIL.MANIFEST_INVALID")

    # Compute run_hash over canonical JSON excluding self-referential fields.
    material = deepcopy(manifest)
    material.pop("run_hash", None)
    material.pop("signature", None)
    computed_run_hash = _sha256_hex(_canonical_json(material))

    recorded = manifest.get("run_hash")
    if not isinstance(recorded, str) or not recorded.strip():
        return OracleResult("FAIL.HASH_MISMATCH", derived={"computed_run_hash": computed_run_hash})
    if computed_run_hash != recorded:
        return OracleResult("FAIL.HASH_MISMATCH", derived={"computed_run_hash": computed_run_hash})

    # Reconciliation: untracked deltas are always a hard failure.
    untracked = manifest.get("untracked_delta_paths")
    if isinstance(untracked, list) and any(untracked):
        return OracleResult("RECON.UNTRACKED_DELTA")

    return OracleResult(PASS, derived={"computed_run_hash": computed_run_hash})


def _oracle_work_completion(vector: dict) -> OracleResult:
    input_obj = vector.get("input")
    if not isinstance(input_obj, dict):
        return OracleResult(CONFVEC_VECTOR_INVALID)

    receipt = input_obj.get("completion_receipt")
    manifest = input_obj.get("evidence_manifest")
    head_commit = input_obj.get("head_commit_sha")
    if not isinstance(receipt, dict) or not isinstance(manifest, dict) or not isinstance(head_commit, str):
        return OracleResult(CONFVEC_VECTOR_INVALID)

    evidence_run_hash = receipt.get("evidence_run_hash")
    if not isinstance(evidence_run_hash, str) or not evidence_run_hash.strip():
        return OracleResult("COMPLETE.EVIDENCE_MISSING")

    # Evidence existence + binding: receipt hash must match manifest run_hash.
    manifest_run_hash = manifest.get("run_hash")
    if not isinstance(manifest_run_hash, str) or not manifest_run_hash.strip():
        return OracleResult("COMPLETE.EVIDENCE_MISSING")
    if evidence_run_hash != manifest_run_hash:
        return OracleResult("COMPLETE.EVIDENCE_MISSING")

    # Evidence validity: manifest run_hash must match computed hash.
    material = deepcopy(manifest)
    material.pop("run_hash", None)
    material.pop("signature", None)
    computed_run_hash = _sha256_hex(_canonical_json(material))
    if computed_run_hash != manifest_run_hash:
        return OracleResult("COMPLETE.EVIDENCE_INVALID", derived={"computed_run_hash": computed_run_hash})

    # Reconciliation: untracked deltas are always a hard completion failure.
    untracked = manifest.get("untracked_delta_paths")
    if isinstance(untracked, list) and any(untracked):
        return OracleResult("COMPLETE.RECON_UNTRACKED_DELTA")

    source_state = manifest.get("source_state")
    receipt_source = receipt.get("verified_source_state")
    if not isinstance(source_state, dict):
        return OracleResult("COMPLETE.SOURCE_STATE_MISSING")
    if not isinstance(receipt_source, dict):
        return OracleResult("COMPLETE.SOURCE_STATE_MISMATCH")

    manifest_commit = source_state.get("commit_sha")
    receipt_commit = receipt_source.get("commit_sha")
    if not isinstance(manifest_commit, str) or not isinstance(receipt_commit, str):
        return OracleResult("COMPLETE.SOURCE_STATE_MISMATCH")
    if manifest_commit != receipt_commit:
        return OracleResult("COMPLETE.SOURCE_STATE_MISMATCH")

    # Head binding at transition time.
    if manifest_commit != head_commit:
        return OracleResult("COMPLETE.SOURCE_NOT_HEAD")

    # Required gates must pass (or explicit exceptions cover).
    plan = manifest.get("plan")
    gates: list[str] = []
    if isinstance(plan, dict) and plan.get("kind") == "inline":
        inline = plan.get("inline")
        if isinstance(inline, dict) and isinstance(inline.get("gates"), list):
            gates = [g for g in inline.get("gates", []) if isinstance(g, str)]

    results = manifest.get("gate_results")
    results_by_id: dict[str, dict] = {}
    if isinstance(results, list):
        for entry in results:
            if isinstance(entry, dict) and isinstance(entry.get("gate_id"), str):
                results_by_id[entry["gate_id"]] = entry

    failing: list[str] = []
    for gate_id in gates:
        result = results_by_id.get(gate_id)
        status = result.get("status") if isinstance(result, dict) else None
        if status != "pass":
            failing.append(gate_id)

    if failing:
        grants = receipt.get("exception_grants")
        if not isinstance(grants, list) or not grants:
            return OracleResult("COMPLETE.EXCEPTION_REQUIRED", derived={"failing_gates": failing})

        covered = {g.get("gate_id") for g in grants if isinstance(g, dict)}
        if any(g not in covered for g in failing):
            return OracleResult("COMPLETE.EXCEPTION_INVALID", derived={"failing_gates": failing})

    return OracleResult(PASS, derived={"computed_run_hash": computed_run_hash})


def _compute_oracle_result(*, vector: dict, spec: str) -> OracleResult:
    if spec == "canonicalization":
        return _oracle_canonicalization(vector)
    if spec == "gate-contract":
        return _oracle_gate_contract(vector)
    if spec == "reconciliation":
        return _oracle_reconciliation(vector)
    if spec == "permit-token":
        return _oracle_permit(vector)
    if spec == "evidence-bundle":
        return _oracle_evidence_bundle(vector)
    if spec == "work-completion":
        return _oracle_work_completion(vector)
    return OracleResult(CONFVEC_ORACLE_UNKNOWN)


def validate_vector(*, path: Path, spec: str, expected_outcome: str) -> tuple[bool, str, list[str]]:
    try:
        vector = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return (False, CONFVEC_VECTOR_INVALID, [f"{CONFVEC_VECTOR_INVALID}: invalid JSON: {e}"])
    except OSError as e:
        return (False, CONFVEC_VECTOR_INVALID, [f"{CONFVEC_VECTOR_INVALID}: read error: {e}"])

    if not isinstance(vector, dict):
        return (False, CONFVEC_VECTOR_INVALID, [f"{CONFVEC_VECTOR_INVALID}: root must be an object"])

    oracle_ref = vector.get("oracle_ref")
    if not isinstance(oracle_ref, str) or not oracle_ref.strip():
        computed_outcome = CONFVEC_ORACLE_MISSING
        if computed_outcome == expected_outcome:
            return (True, computed_outcome, [])
        return (
            False,
            computed_outcome,
            [f"{CONFVEC_OUTCOME_MISMATCH}: expected {expected_outcome}, got {computed_outcome}"],
        )

    oracle_spec, _version, _oracle_name = _parse_oracle_ref(oracle_ref)
    if oracle_spec != spec:
        computed_outcome = CONFVEC_ORACLE_UNKNOWN
        if computed_outcome == expected_outcome:
            return (True, computed_outcome, [])
        return (
            False,
            computed_outcome,
            [f"{CONFVEC_OUTCOME_MISMATCH}: expected {expected_outcome}, got {computed_outcome}"],
        )

    # Oracle determinism check: run twice and compare.
    r1 = _compute_oracle_result(vector=vector, spec=spec)
    r2 = _compute_oracle_result(vector=vector, spec=spec)
    if r1 != r2:
        computed_outcome = CONFVEC_ORACLE_NONDETERMINISTIC
        if computed_outcome == expected_outcome:
            return (True, computed_outcome, [])
        return (
            False,
            computed_outcome,
            [f"{CONFVEC_OUTCOME_MISMATCH}: expected {expected_outcome}, got {computed_outcome}"],
        )

    computed_outcome = r1.outcome
    if computed_outcome != expected_outcome:
        return (
            False,
            computed_outcome,
            [f"{CONFVEC_OUTCOME_MISMATCH}: expected {expected_outcome}, got {computed_outcome}"],
        )

    # Suite-level expectation matched.
    return (True, computed_outcome, [])


def main() -> int:
    script_dir = Path(__file__).parent
    repo_root = script_dir.parent
    index_path = script_dir / "index.json"

    if not index_path.exists():
        print(f"ERROR: conformance index not found: {index_path}")
        return 1

    index = json.loads(index_path.read_text(encoding="utf-8"))
    vectors = index.get("vectors")
    if not isinstance(vectors, list):
        print(f"ERROR: invalid conformance index (missing vectors list): {index_path}")
        return 1

    total = 0
    passed = 0
    failed = 0

    for entry in vectors:
        total += 1
        file_rel = entry.get("file")
        spec = entry.get("spec")
        expected = entry.get("expected")
        if not isinstance(file_rel, str) or not isinstance(spec, str) or not isinstance(expected, str):
            failed += 1
            print(f"FAIL: (index entry malformed) {entry!r}")
            continue

        path = repo_root / "conformance" / file_rel
        ok, computed_outcome, errors = validate_vector(path=path, spec=spec, expected_outcome=expected)

        if ok:
            passed += 1
            print(f"PASS: {Path(file_rel).name} ({computed_outcome})")
        else:
            failed += 1
            print(f"FAIL: {Path(file_rel).name} ({computed_outcome})")
            for error in errors:
                print(f"      {error}")

    print()
    print(f"Total: {total}, Passed: {passed}, Failed: {failed}")
    if failed:
        return 1
    print("All vectors valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
