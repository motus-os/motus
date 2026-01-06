# Conformance Vector Validity (CORE-CONF-002)

> **Status:** Draft | **Version:** 0.1.0 | **Last Updated:** 2025-12-15

## Purpose

Motus standards must **validate themselves**. A conformance suite that is syntactically valid but semantically wrong is
governance theater.

This specification defines requirements for **conformance vector validity** so that:

1. Every conformance vector has a deterministic **oracle** that can be run by any verifier.
2. A validator can fail-closed when a vector is incomplete, ambiguous, or incorrect.

## Definitions

- **Conformance vector:** A JSON file under `conformance/vectors/` referenced by `conformance/index.json`.
- **Protocol oracle (O):** A deterministic function that maps `vector.input` to:
  - an **outcome** reason code (e.g., `PASS`, `FAIL.HASH_MISMATCH`)
  - optional **derived fields** (e.g., canonical JSON, computed hash, reconciliation result)
- **oracle_ref:** A required string pointer to the oracle in the form:
  - `<spec>@<version>#<oracle>`
  - Example: `canonicalization@0.1.0#canonicalize_sha256`

## Invariants (minimum)

### INV-1 — Vector validity (schema-level)

Vectors MUST:
- be valid JSON
- include `oracle_ref` (string)
- include `input` (object)
- include `expected_outcome` (string)

### INV-2 — Oracle determinism

For any vector `v`, `O(v.input)` MUST be deterministic:
- `O(v.input)` run twice MUST produce identical results.

### INV-3 — Derived-field correctness

If a vector declares expected derived fields (e.g., `expected_canonical`, `expected_hash`, `expected_result`), then
the validator MUST confirm that:

`derived_fields == expected_*`

Mismatch MUST fail-closed.

### INV-4 — Outcome correctness

The validator MUST compare oracle outcome to the expected outcome (from the vector and/or suite index) and fail if they
do not match.

### INV-5 — Reason code constraints

Outcomes and validator errors MUST be stable reason codes present in `reason-codes/reason-codes.json`.

### INV-6 — Self-containment

The reference validator MUST:
- run without network access
- use only the standard library
- avoid environment-dependent behavior (deterministic ordering)

## Reason Codes

Validator-level failures use the `CONFVEC.*` namespace:

- `CONFVEC.ORACLE_MISSING` — `oracle_ref` missing
- `CONFVEC.ORACLE_UNKNOWN` — `oracle_ref` unrecognized/unsupported
- `CONFVEC.ORACLE_NONDETERMINISTIC` — oracle produced non-deterministic output
- `CONFVEC.VECTOR_INVALID` — missing required fields or invalid types
- `CONFVEC.DERIVED_MISMATCH` — derived fields do not match expected
- `CONFVEC.OUTCOME_MISMATCH` — computed outcome != expected outcome

## Validator Contract

`python3 conformance/validate.py` MUST:

1. Treat `conformance/index.json` as the suite source-of-truth
2. Validate each referenced vector via its oracle
3. Print PASS/FAIL per vector (deterministic ordering)
4. Exit non-zero if any vector fails

## Related Specifications

- [Canonicalization](canonicalization.md)
- [Evidence Bundle](evidence-bundle.md)
- [Gate Contract](gate-contract.md)
- [Reconciliation](reconciliation.md)
- [Permit Token](permit-token.md)
