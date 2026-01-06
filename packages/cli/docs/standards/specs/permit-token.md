# Permit Token Specification

> **Status:** Draft | **Version:** 0.1.0 | **Last Updated:** 2025-12-15

---

## Purpose

A **permit token** authorizes a specific side-effecting action within an approved plan. It enforces:

> **No permit → No run**

Side effects (file writes, API calls, command execution) require explicit authorization bound to a sealed plan.

---

## The Problem

Without permits:

1. Agent receives a plan with gates
2. Gates pass
3. Agent can still execute any action afterward
4. "Governed" work can happen outside the gate pipeline

This is the **bypass risk** — work logged after the fact, not gated in advance.

With permits:

1. Plan is sealed
2. Permits issued for specific actions
3. Each action requires a valid permit
4. Unpermitted actions fail immediately

---

## Permit Structure

```json
{
  "permit_id": "permit-2025-12-15-xyz789",
  "seal_id": "seal-2025-12-15-abc123",
  "action": {
    "type": "file_write",
    "target": "src/main.py"
  },
  "constraints": {
    "max_size_bytes": 10000,
    "allowed_operations": ["modify", "create"]
  },
  "issued_at": "2025-12-15T10:30:05Z",
  "expires_at": "2025-12-15T10:35:05Z",
  "permit_hash": "sha256:def456..."
}
```

### Permit Fields

| Field | Type | Description |
|-------|------|-------------|
| `permit_id` | string | Unique permit identifier |
| `seal_id` | string | Plan seal this permit is bound to |
| `action` | object | The authorized action |
| `constraints` | object | Limits on the action |
| `issued_at` | string | When permit was created |
| `expires_at` | string | When permit becomes invalid |
| `permit_hash` | string | Hash for verification |

---

## Action Types

| Type | Target | Description |
|------|--------|-------------|
| `file_write` | path | Write to filesystem |
| `file_delete` | path | Delete from filesystem |
| `command_exec` | command | Execute shell command |
| `api_call` | endpoint | Call external API |
| `tool_invoke` | tool_name | Invoke agent tool |

### Example: File Write Permit

```json
{
  "action": {
    "type": "file_write",
    "target": "src/auth/login.py"
  },
  "constraints": {
    "max_size_bytes": 50000,
    "allowed_operations": ["modify"]
  }
}
```

### Example: Command Execution Permit

```json
{
  "action": {
    "type": "command_exec",
    "target": "pytest tests/ -q"
  },
  "constraints": {
    "timeout_ms": 300000,
    "allowed_exit_codes": [0, 1]
  }
}
```

---

## Permit Lifecycle

```
┌─────────────────────────────────────────────────────┐
│                    Plan Sealed                       │
└───────────────────────┬─────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────┐
│              Permits Issued for Actions              │
│                                                      │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐              │
│  │Permit A │  │Permit B │  │Permit C │              │
│  │(write)  │  │(test)   │  │(deploy) │              │
│  └─────────┘  └─────────┘  └─────────┘              │
└───────────────────────┬─────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────┐
│                  Execution Phase                     │
│                                                      │
│  Action → Check Permit → Execute if Valid            │
│                                                      │
└───────────────────────┬─────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────┐
│                 Evidence Records                     │
│           Permit References in Bundle                │
└─────────────────────────────────────────────────────┘
```

---

## Enforcement

### Before Each Action

```python
def execute_with_permit(action, permit):
    """Execute action only if permit is valid."""

    # Check permit exists
    if permit is None:
        raise PermitError("NO_PERMIT")

    # Check permit matches action
    if not permit_matches_action(permit, action):
        raise PermitError("PERMIT_MISMATCH")

    # Check permit not expired
    if now() > permit.expires_at:
        raise PermitError("PERMIT_EXPIRED")

    # Check constraints
    if not constraints_satisfied(action, permit.constraints):
        raise PermitError("CONSTRAINT_VIOLATION")

    # Execute action
    return execute(action)
```

### Failure Modes

| Error | Meaning |
|-------|---------|
| `NO_PERMIT` | Action attempted without any permit |
| `PERMIT_MISMATCH` | Permit doesn't authorize this action |
| `PERMIT_EXPIRED` | Permit time window has passed |
| `SEAL_MISMATCH` | Permit's seal doesn't match current plan |
| `CONSTRAINT_VIOLATION` | Action exceeds permit constraints |

---

## Evidence Recording

Permits are recorded in evidence (paths only):

```json
{
  "permits_used": [
    {
      "permit_id": "permit-2025-12-15-xyz789",
      "action_type": "file_write",
      "target": "src/main.py",
      "status": "consumed"
    }
  ],
  "unpermitted_attempts": []
}
```

### Unpermitted Attempts

If an action is attempted without a permit:

```json
{
  "unpermitted_attempts": [
    {
      "action_type": "file_write",
      "target": "README.md",
      "attempted_at": "2025-12-15T10:32:00Z",
      "result": "blocked"
    }
  ]
}
```

---

## Constraints

Permits can limit actions beyond simple authorization:

### File Constraints

| Constraint | Description |
|------------|-------------|
| `max_size_bytes` | Maximum file size |
| `allowed_operations` | create, modify, delete |
| `path_pattern` | Glob pattern for paths |

### Command Constraints

| Constraint | Description |
|------------|-------------|
| `timeout_ms` | Maximum execution time |
| `allowed_exit_codes` | Acceptable exit codes |
| `env_allowlist` | Environment variables allowed |

### API Constraints

| Constraint | Description |
|------------|-------------|
| `max_requests` | Request count limit |
| `rate_limit_ms` | Minimum time between requests |
| `allowed_methods` | HTTP methods allowed |

---

## Security Considerations

### Permit Forgery Prevention

Permits should be:

1. **Cryptographically bound** to seal (seal_id in hash)
2. **Signed** if high-trust profile requires
3. **Short-lived** (minutes, not hours)

### Principle of Least Authority

Permits should be:

1. **Specific** — one action per permit, not blanket authorization
2. **Constrained** — limits on size, time, operations
3. **Minimal** — only permits needed for the plan

### Audit Trail

All permits must be:

1. **Recorded** in evidence bundle
2. **Traceable** to the issuing seal
3. **Immutable** after issuance

---

## Implementation Status

This specification is **draft** (Phase 0.1.3). Current status:

- [ ] Permit structure defined
- [ ] Enforcement hooks specified
- [ ] Evidence recording specified
- [ ] Reference implementation
- [ ] Conformance tests

Until permits are implemented, the **bypass risk** remains: work can happen outside Motus and only be logged after the fact.

---

## Compatibility

| Version | Status | Notes |
|---------|--------|-------|
| 1.0.0 | Draft | Initial specification |

---

## Related Specifications

- [Plan Seal](plan-seal.md) — Permits are bound to seals
- [Evidence Bundle](evidence-bundle.md) — Records permit usage
- [Gate Contract](gate-contract.md) — Gates run before permit issuance
- [Reconciliation](reconciliation.md) — Scope enforcement complements permits
