# Work Completion Binding Specification

> **Status:** Draft | **Version:** 0.1.0 | **Last Updated:** 2025-12-15

---

## Purpose

Prevent “stale verification” and “unprovable DONE claims.”

A work item may be declared **DONE** only if the declaration is bound to:
- a **specific immutable source state** (e.g., git commit),
- a **verifiable EvidenceBundle** (hashes + verifier PASS),
- and the **required gate outcomes** for that work (or explicit, bounded exceptions).

This is the same failure class as conformance-vector theater:
> “Structurally valid artifacts that are semantically ungrounded.”

---

## Required Artifacts

### 1) EvidenceBundle (existing)

See: `specs/evidence-bundle.md`

This spec additionally requires the EvidenceManifest to include `source_state` (SOURCE-STATE-001) for completion claims.

### 2) CompletionReceipt (new)

Schema: `schemas/completion-receipt.json`

The CompletionReceipt is the auditable “journal entry” for a terminal state transition (e.g., CR → `done/`).

---

## SOURCE-STATE-001 (Evidence Manifest extension)

Add `source_state` to the EvidenceManifest:
- required for WORK-COMPLETE-001 semantics,
- optional for general EvidenceBundles (backward compatible).

Shape (see `schemas/evidence-manifest.json`):
- `vcs`: `"git"`
- `commit_sha`: 40-hex commit SHA of `repo_dir` HEAD at runtime
- `ref`: optional ref name (e.g., `refs/heads/main`)
- `dirty`: whether the repo had uncommitted changes at runtime

**Recommended policy for DONE claims:** `dirty=false`.

---

## Invariants (non-ceremonial)

Let:
- `C` = CompletionReceipt
- `E` = EvidenceManifest referenced by `C`
- `V(E)` = Evidence verifier output for `E` (PASS/FAIL with reason codes)
- `G` = required gate IDs for the run (from `E.plan.inline.gates`)
- `HEAD(target_ref)` = commit SHA of the target ref at transition time (enforceable in CI)

### INV-1: Evidence existence

`C.evidence_run_hash` MUST be present and MUST match `E.run_hash`.

### INV-2: Evidence validity

`V(E)` MUST be `PASS`.

### INV-3: Reconciliation respected (if present/required)

If `E.untracked_delta_paths` is present and non-empty, completion MUST fail.

### INV-4: Required gates satisfied (or explicit exceptions)

For every gate `g ∈ G`, `E.gate_results[g].status` MUST be `pass`,
unless an explicit exception grant covers the failure (see “Exceptions”).

### INV-5: State binding

`C.verified_source_state` MUST equal `E.source_state`.

### INV-6: Head binding at transition time

At transition time:

`E.source_state.commit_sha == HEAD(C.target_ref)`

If `HEAD(target_ref)` cannot be evaluated, completion MUST be denied or require a trusted CI attestation.

---

## Enforcement Points

This spec is only real if it is enforced **fail-closed**:
- CI must block any change that transitions work to DONE without a valid CompletionReceipt bound to verifiable evidence.
- Local tooling MAY assist, but CI enforcement is the durable choke point.

---

## Reason Codes

This spec introduces `COMPLETE.*` codes (see `reason-codes/reason-codes.json`), including:
- `COMPLETE.EVIDENCE_MISSING`
- `COMPLETE.EVIDENCE_INVALID`
- `COMPLETE.SOURCE_STATE_MISSING`
- `COMPLETE.SOURCE_STATE_MISMATCH`
- `COMPLETE.SOURCE_NOT_HEAD`
- `COMPLETE.GATE_FAILED`
- `COMPLETE.EXCEPTION_REQUIRED`
- `COMPLETE.EXCEPTION_INVALID`
- `COMPLETE.RECON_UNTRACKED_DELTA`

---

## Conformance

Conformance vectors are required (and must be oracle-backed per CORE-CONF-002):
- `conformance/vectors/complete-T01.json` … `complete-T06.json`

---

## Exceptions (optional)

Exceptions are allowed only if they are explicit, bounded, and auditable.

This spec supports exceptions as `exception_grants[]` on the CompletionReceipt, but stronger semantics (signatures, expiry, scope) should be defined by a dedicated spec (e.g., EXCEPT-GRANT-001) before treating exceptions as high-trust.

