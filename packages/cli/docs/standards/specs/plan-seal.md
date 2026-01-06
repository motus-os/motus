# Plan Seal Specification

> **Status:** Draft | **Version:** 0.1.0 | **Last Updated:** 2025-12-15

---

## Purpose

A **plan seal** is an immutable commitment to a gate plan before execution begins. It prevents:

1. **Plan drift** — changing the plan mid-execution
2. **Retroactive justification** — claiming different gates were required
3. **Scope expansion** — adding files to scope after changes are made

---

## Concept

```
                    ┌─────────────┐
                    │   Planning  │
                    │   Phase     │
                    └──────┬──────┘
                           │
                           ▼
                    ┌─────────────┐
                    │  Plan Seal  │ ← Immutable commitment
                    │  Created    │
                    └──────┬──────┘
                           │
                           ▼
                    ┌─────────────┐
                    │  Execution  │
                    │   Phase     │
                    └─────────────┘
```

Once sealed, the plan cannot be modified. Execution must follow the sealed plan exactly.

---

## Seal Structure

```json
{
  "seal_id": "seal-2025-12-15-abc123",
  "created_at": "2025-12-15T10:30:00Z",
  "plan_hash": "sha256:abc123...",
  "plan": {
    "version": "1.0.0",
    "packs": ["BP-PACK-CODE"],
    "gate_tier": "T1",
    "gates": ["gate-lint", "gate-test"],
    "scope": ["src/**", "tests/**"]
  },
  "policy_versions": {
    "skill_packs_registry": "1.0.0",
    "gates": "1.0.0"
  }
}
```

### Seal Fields

| Field | Type | Description |
|-------|------|-------------|
| `seal_id` | string | Unique identifier for this seal |
| `created_at` | string | ISO 8601 timestamp |
| `plan_hash` | string | SHA-256 of canonical plan JSON |
| `plan` | object | The sealed gate plan |
| `policy_versions` | object | Policy artifact versions at seal time |

---

## Sealing Process

### Step 1: Compute Plan

```python
plan = compute_gate_plan(
    changed_files=["src/main.py", "tests/test_main.py"],
    profile="personal",
    policy_artifacts=load_policy()
)
```

### Step 2: Create Seal

```python
seal = PlanSeal(
    seal_id=generate_seal_id(),
    created_at=now(),
    plan=plan,
    plan_hash=hash_canonical_json(plan),
    policy_versions=get_policy_versions()
)
```

### Step 3: Store Seal

```python
store_seal(seal)  # Immutable storage
```

### Step 4: Execute Against Seal

```python
for gate in seal.plan.gates:
    result = run_gate(gate)
    if result.status == "fail":
        break  # Fail-closed
```

---

## Verification

When verifying an evidence bundle, check that execution matched the seal:

```python
def verify_seal_compliance(evidence, seal):
    """Verify execution followed the sealed plan."""

    # Check plan matches seal
    if evidence.plan != seal.plan:
        return VerifyResult.FAIL("SEAL.PLAN_MISMATCH")

    # Check all sealed gates were executed
    executed_gates = {r.gate_id for r in evidence.gate_results}
    sealed_gates = set(seal.plan.gates)

    if not sealed_gates.issubset(executed_gates):
        missing = sealed_gates - executed_gates
        return VerifyResult.FAIL(f"SEAL.MISSING_GATES: {missing}")

    # Check scope wasn't expanded
    if evidence.workspace_delta_paths:
        for path in evidence.workspace_delta_paths:
            if not matches_scope(path, seal.plan.scope):
                return VerifyResult.FAIL("SEAL.SCOPE_VIOLATION")

    return VerifyResult.PASS()
```

---

## Failure Modes

| Failure | Meaning |
|---------|---------|
| `SEAL.PLAN_MISMATCH` | Executed plan differs from sealed plan |
| `SEAL.MISSING_GATES` | Not all sealed gates were executed |
| `SEAL.SCOPE_VIOLATION` | Changes made outside sealed scope |
| `SEAL.POLICY_DRIFT` | Policy versions changed after sealing |

---

## Relationship to Permits

Plan seals enable permits (see [Permit Token](permit-token.md)):

1. **Seal created** → Plan is locked
2. **Permits issued** → Authorized actions reference the seal
3. **Execution happens** → Actions validated against permits
4. **Evidence produced** → References the seal

```
Plan Seal ─────┬───→ Permit A (for tool X)
               ├───→ Permit B (for tool Y)
               └───→ Permit C (for tool Z)
```

---

## Storage Requirements

Plan seals MUST be:

1. **Immutable** — Cannot be modified after creation
2. **Durable** — Persist for audit trail
3. **Addressable** — Retrievable by seal_id

Storage options:
- Append-only log file
- Database with write-once semantics
- Content-addressed storage (hash-based)

---

## Compatibility

| Version | Status | Notes |
|---------|--------|-------|
| 1.0.0 | Draft | Initial specification |

---

## Related Specifications

- [Evidence Bundle](evidence-bundle.md) — References seal in evidence
- [Gate Contract](gate-contract.md) — Gates defined in sealed plan
- [Permit Token](permit-token.md) — Permits bound to seals
- [Reconciliation](reconciliation.md) — Scope from sealed plan
