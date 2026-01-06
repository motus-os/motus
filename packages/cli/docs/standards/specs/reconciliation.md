# Reconciliation Specification (D ⊆ R)

> **Status:** Stable | **Version:** 0.1.0 | **Last Updated:** 2025-12-15

---

## Purpose

**Reconciliation** enforces that workspace changes stay within declared scope:

> **D ⊆ R** — Delta must be a subset of Requested scope

When an agent claims "I only touched X," reconciliation makes that a verifiable assertion.

---

## The Problem

Without scope enforcement:

1. Agent is asked to "fix the login bug"
2. Agent also "cleans up" unrelated files
3. Reviewer can't tell what was intentional vs. accidental
4. Blame is ambiguous if something breaks

With reconciliation:

1. Agent declares scope: `src/auth/login.py`
2. Agent makes changes
3. System detects all changed paths
4. If changes exist outside scope → FAIL with `RECON.UNTRACKED_DELTA`

---

## Definitions

| Symbol | Name | Meaning |
|--------|------|---------|
| **R** | Requested | Scope declared at run start |
| **D** | Delta | Paths actually changed during run |
| **D ⊆ R** | Constraint | Delta must be subset of Requested |

### Scope Declaration

Scope is declared as glob patterns:

```json
{
  "scope": [
    "src/auth/**",
    "tests/test_auth.py"
  ]
}
```

### Delta Detection

Delta is computed by comparing workspace state:

1. **Before run:** Snapshot workspace (file hashes or git status)
2. **After run:** Snapshot workspace again
3. **Compute delta:** Files that changed (added, modified, deleted)

---

## Algorithm

```python
def reconcile(requested_scope: List[str], delta_paths: List[str]) -> ReconciliationResult:
    """
    Check that all changed paths are within declared scope.

    Args:
        requested_scope: Glob patterns for allowed changes
        delta_paths: Paths that actually changed

    Returns:
        ReconciliationResult with pass/fail and untracked paths
    """
    untracked = []

    for path in delta_paths:
        if not matches_any_pattern(path, requested_scope):
            untracked.append(path)

    if untracked:
        return ReconciliationResult(
            status="fail",
            reason="RECON.UNTRACKED_DELTA",
            untracked_delta_paths=untracked
        )

    return ReconciliationResult(
        status="pass",
        reason=None,
        untracked_delta_paths=[]
    )
```

---

## Evidence Recording

Reconciliation results are recorded in the evidence manifest:

```json
{
  "workspace_delta_paths": [
    "src/auth/login.py",
    "tests/test_auth.py",
    "src/utils/helper.py"  // Out of scope!
  ],
  "untracked_delta_paths": [
    "src/utils/helper.py"
  ]
}
```

### Verification Failure

When `untracked_delta_paths` is non-empty:

1. **Run status:** FAIL
2. **Reason code:** `RECON.UNTRACKED_DELTA`
3. **Evidence:** Still written (failure is recorded, not hidden)
4. **Action:** Run cannot be marked as "done"

---

## Scope Patterns

### Glob Syntax

| Pattern | Matches |
|---------|---------|
| `src/*.py` | Python files directly in src/ |
| `src/**/*.py` | Python files anywhere under src/ |
| `tests/test_*.py` | Test files in tests/ |
| `*.md` | Markdown files in root |
| `**/*.md` | Markdown files anywhere |

### Special Cases

| Pattern | Meaning |
|---------|---------|
| `*` | All files in current directory |
| `**` | All files recursively |
| `!pattern` | Exclude pattern (if supported) |

---

## Integration with Gate Plan

Scope flows from skill packs to reconciliation:

```
Changed Files → Skill Packs → Scope Patterns → Gate Plan
                                    ↓
                              Reconciliation
                                    ↓
                             D ⊆ R Check
```

### Pack Scope Example

```json
{
  "id": "BP-PACK-CODE",
  "scope": [
    "src/**",
    "tests/**",
    "pyproject.toml",
    "package.json"
  ]
}
```

If the plan includes `BP-PACK-CODE`, those scope patterns are added to R.

---

## Handling Violations

### Detection

Violations are detected during evidence generation:

```python
# After all gates complete
delta = compute_workspace_delta(snapshot_before, snapshot_after)
result = reconcile(plan.scope, delta)

evidence.workspace_delta_paths = delta
evidence.untracked_delta_paths = result.untracked_delta_paths

if result.untracked_delta_paths:
    evidence.status = "fail"
    evidence.reason = "RECON.UNTRACKED_DELTA"
```

### Response Options

When scope creep is detected:

1. **Expand scope** — Re-run with broader scope declaration
2. **Revert changes** — Undo out-of-scope changes, re-run
3. **Split work** — Create separate run for out-of-scope changes

### What NOT to Do

- Do NOT suppress untracked deltas silently
- Do NOT edit evidence to remove violations
- Do NOT skip reconciliation in "fast mode"

---

## Use Cases

### Case 1: Clean Run

```
Requested: ["src/auth/**"]
Delta: ["src/auth/login.py", "src/auth/session.py"]
Result: PASS (D ⊆ R)
```

### Case 2: Scope Creep

```
Requested: ["src/auth/**"]
Delta: ["src/auth/login.py", "README.md"]
Result: FAIL (README.md not in scope)
untracked_delta_paths: ["README.md"]
```

### Case 3: Empty Delta

```
Requested: ["src/auth/**"]
Delta: []
Result: PASS (empty set is subset of any set)
```

### Case 4: Wildcard Scope

```
Requested: ["**"]
Delta: ["anything.py", "anywhere/file.txt"]
Result: PASS (everything is in scope)
```

---

## Security Considerations

### Scope Should Be Minimal

Broad scope (`**`) defeats the purpose. Best practice:

- Declare only paths the agent needs to modify
- Use specific patterns, not wildcards
- Review scope before approving runs

### Reconciliation Cannot Be Bypassed

If reconciliation is not enforced:

- Agents can modify any file
- Evidence claims scope compliance but doesn't prove it
- "I only touched X" becomes unverifiable

---

## Compatibility

| Version | Status | Notes |
|---------|--------|-------|
| 1.0.0 | Stable | Initial release |

---

## Related Specifications

- [Evidence Bundle](evidence-bundle.md) — Records reconciliation results
- [Gate Contract](gate-contract.md) — Runs before reconciliation
- [Plan Seal](plan-seal.md) — Locks scope before execution
