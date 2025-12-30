# Coordination API (6-call facade)
Status: ACTIVE
Owner: DOCS_SPECS
Scope: 6-call coordination facade overview
Version: 0.1
Date: 2025-12-30

Motus exposes a single coordination surface used by the CLI, SDKs, and bundled
modules. Terminology lives in `docs/TERMINOLOGY.md`. This page is the high-level entry
point for integrators.

## Canonical calls

| Call | Purpose | Notes |
|------|---------|-------|
| `claim_work` | Reserve a work item and obtain a contract | Returns missing prerequisites |
| `get_context` | Assemble the current lens for the attempt | Returns missing prerequisites |
| `put_outcome` | Register primary deliverables | Outcome is not evidence |
| `record_evidence` | Attach verification artifacts | Typed + hashed evidence |
| `record_decision` | Append reasoning and approvals | Append-only |
| `release_work` | Finalize the attempt | Requires disposition + links |

## Expected flow

1. `claim_work(...)` to reserve an item and receive the initial contract.
2. `get_context(...)` to assemble the latest lens (standards, policy, deps).
3. `put_outcome(...)` to register primary deliverables.
4. `record_evidence(...)` to attach proof (tests, diffs, logs).
5. `record_decision(...)` to record approvals or key reasoning.
6. `release_work(...)` to finalize with disposition and references.

## Design constraints

- **Single surface**: no alternative public APIs beyond the 6-call facade.
- **Deterministic guidance**: calls return `missing_prereqs` so callers do not
  guess next actions.
- **Coordination.db is truth**: all state is stored in `~/.motus/coordination.db`.

## See also

- `docs/TERMINOLOGY.md` (canonical terms)
