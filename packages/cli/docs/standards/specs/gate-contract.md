# Gate Contract Specification

> **Status:** Stable | **Version:** 0.1.0 | **Last Updated:** 2025-12-15

---

## Purpose

A **gate** is an executable verification step in the governance pipeline. Gates:

1. Run as subprocesses with controlled inputs
2. Produce deterministic pass/fail outcomes
3. Generate logs that become part of the evidence bundle

---

## Gate Interface

### Invocation

Gates are invoked as shell commands with environment variables:

```bash
# Example: lint gate
ruff check src/
```

### Environment

Gates receive a sanitized environment:

| Variable | Description | Required |
|----------|-------------|----------|
| `MOTUS_RUN_ID` | Current run identifier | Yes |
| `MOTUS_REPO_DIR` | Repository root path | Yes |
| `MOTUS_GATE_ID` | Gate identifier | Yes |
| `PATH` | System PATH (inherited) | Yes |
| `HOME` | User home directory | Yes |
| `USER` | Current user | Yes |

**Security:** Signing keys (`MC_EVIDENCE_SIGNING_KEY`) and other secrets MUST NOT be passed to gate subprocesses.

### Exit Codes

| Exit Code | Meaning | Evidence Status |
|-----------|---------|-----------------|
| 0 | Gate passed | `pass` |
| Non-zero | Gate failed | `fail` |

### Output Capture

- `stdout` → captured to `logs/{gate_id}.stdout`
- `stderr` → captured to `logs/{gate_id}.stderr`

Logs are referenced by path in evidence; raw content is not embedded in manifest.

---

## Gate Definition Schema

Gates are defined in `gates.json`:

```json
{
  "version": "1.0.0",
  "gates": [
    {
      "id": "gate-lint",
      "name": "Lint Check",
      "command": "ruff check src/",
      "tier": "T0",
      "timeout_ms": 30000,
      "required": true
    },
    {
      "id": "gate-test",
      "name": "Test Suite",
      "command": "pytest tests/ -q",
      "tier": "T1",
      "timeout_ms": 300000,
      "required": true
    },
    {
      "id": "gate-typecheck",
      "name": "Type Check",
      "command": "mypy src/",
      "tier": "T2",
      "timeout_ms": 60000,
      "required": false
    }
  ]
}
```

### Gate Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique gate identifier |
| `name` | string | Human-readable name |
| `command` | string | Shell command to execute |
| `tier` | string | Gate tier (T0, T1, T2) |
| `timeout_ms` | integer | Maximum execution time |
| `required` | boolean | Whether gate failure blocks the run |

---

## Gate Tiers

Tiers organize gates by verification depth:

| Tier | Name | Purpose | Typical Gates |
|------|------|---------|---------------|
| T0 | Fast | Quick sanity checks | lint, format check |
| T1 | Standard | Core verification | tests, type check |
| T2 | Thorough | Deep analysis | security scan, coverage |

### Tier Selection

The gate plan selects which tier to run based on:

1. **Profile configuration** (e.g., `personal` defaults to T0)
2. **Skill pack overrides** (e.g., code pack escalates to T1)
3. **Explicit request** (e.g., `--tier T2`)

---

## Execution Model

### Order

Gates execute in order as defined in the plan:

```
gate-lint (T0) → gate-test (T1) → gate-typecheck (T2)
```

### Fail-Closed

If any required gate fails:

1. Execution stops immediately
2. Remaining gates are skipped (status: `skip`)
3. Evidence bundle is still written (with failure recorded)
4. Overall run status is `FAIL`

### Timeout

If a gate exceeds `timeout_ms`:

1. Subprocess is killed
2. Gate is marked as `fail` with exit code -1
3. Execution continues to fail-closed behavior

---

## Evidence Generation

Each gate produces a result entry:

```json
{
  "gate_id": "gate-lint",
  "status": "pass",
  "exit_code": 0,
  "duration_ms": 245,
  "log_paths": ["logs/gate-lint.stdout", "logs/gate-lint.stderr"]
}
```

### Status Values

| Status | Meaning |
|--------|---------|
| `pass` | Gate completed with exit code 0 |
| `fail` | Gate completed with non-zero exit code |
| `skip` | Gate was not executed (prior failure or config) |

---

## Writing Custom Gates

### Requirements

A valid gate must:

1. **Be deterministic** — same inputs produce same outputs
2. **Exit cleanly** — use proper exit codes (0 = pass, non-zero = fail)
3. **Write to stdout/stderr** — output is captured as evidence
4. **Respect timeout** — complete within configured time
5. **Not require secrets** — no API keys or credentials needed

### Example: Custom Security Gate

```bash
#!/bin/bash
# gate-security.sh

set -e

# Check for hardcoded secrets
if grep -r "API_KEY\s*=" src/; then
  echo "ERROR: Hardcoded API key detected"
  exit 1
fi

# Check for known vulnerable patterns
if grep -r "eval(" src/; then
  echo "ERROR: eval() usage detected"
  exit 1
fi

echo "Security check passed"
exit 0
```

Register in `gates.json`:

```json
{
  "id": "gate-security",
  "name": "Security Scan",
  "command": "./gates/gate-security.sh",
  "tier": "T1",
  "timeout_ms": 30000,
  "required": true
}
```

---

## Security Considerations

### Environment Sanitization

Gate subprocesses receive only allowlisted environment variables:

```
ALLOWLIST = [PATH, HOME, USER, SHELL, LANG, LC_*, MOTUS_*]
```

All other variables (especially `*_KEY`, `*_SECRET`, `*_TOKEN`) are stripped.

### Command Injection

Gate commands should not include user-controlled input. If parameterization is needed:

1. Use environment variables (from allowlist only)
2. Validate all parameters before execution
3. Avoid shell interpolation where possible

---

## Compatibility

| Version | Status | Notes |
|---------|--------|-------|
| 1.0.0 | Stable | Initial release |

---

## Related Specifications

- [Evidence Bundle](evidence-bundle.md) — Format for gate results
- [Reconciliation](reconciliation.md) — Scope enforcement
- [Plan Seal](plan-seal.md) — Immutable plan commitment
