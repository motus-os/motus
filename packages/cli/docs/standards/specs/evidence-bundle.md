# Evidence Bundle Specification

> **Status:** Stable | **Version:** 0.1.0 | **Last Updated:** 2025-12-15

---

## Purpose

An **evidence bundle** is the tamper-evident record of a governed agent run. It answers:

1. **What was planned?** (gate plan, policy versions)
2. **What happened?** (gate results, exit codes, durations)
3. **What changed?** (workspace delta paths)
4. **Can we verify it?** (hashes, signatures, chain-of-work)

---

## Bundle Structure

```
evidence/
├── manifest.json          # Required: structured evidence record
└── logs/                   # Optional: gate execution logs
    ├── gate-lint.stdout
    ├── gate-lint.stderr
    ├── gate-test.stdout
    └── gate-test.stderr
```

---

## Manifest Schema

The `manifest.json` file follows this structure:

### Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `version` | string | Schema version (e.g., "1.0.0") |
| `run_id` | string | Unique identifier for this run |
| `created_at` | string | ISO 8601 timestamp |
| `repo_dir` | string | Absolute path to repository root |
| `policy_versions` | object | Versions of policy artifacts used |
| `plan` | object | Gate plan (inline or path reference) |
| `gate_results` | array | Per-gate execution results |

### Verifiability Fields (Recommended)

| Field | Type | Description |
|-------|------|-------------|
| `run_hash` | string | SHA-256 over canonical manifest (excluding signature) |
| `prev_run_hash` | string | Link to prior run (chain-of-work) |
| `artifact_hashes` | array | SHA-256 hashes for evidence artifacts |
| `signature` | string | Signature over `run_hash` |
| `key_id` | string | Identifier for signing key |

### Reconciliation Fields (Recommended)

| Field | Type | Description |
|-------|------|-------------|
| `workspace_delta_paths` | array | Paths that changed during the run |
| `untracked_delta_paths` | array | Changed paths outside declared scope |

### Budget Fields (Optional)

| Field | Type | Description |
|-------|------|-------------|
| `budgets.tokens` | integer | Token count consumed |
| `budgets.cost_usd` | number | Estimated cost in USD |
| `budgets.tool_calls` | integer | Number of tool invocations |

---

## Example Manifest

```json
{
  "version": "1.0.0",
  "run_id": "run-2025-12-15-a1b2c3",
  "created_at": "2025-12-15T10:30:00Z",
  "repo_dir": "/home/user/project",
  "profile_id": "personal",

  "policy_versions": {
    "skill_packs_registry": "1.0.0",
    "gates": "1.0.0"
  },

  "plan": {
    "kind": "inline",
    "inline": {
      "version": "1.0.0",
      "policy_versions": {
        "skill_packs_registry": "1.0.0",
        "gates": "1.0.0"
      },
      "packs": ["BP-PACK-CODE"],
      "pack_versions": [
        {
          "id": "BP-PACK-CODE",
          "version": "1.0.0",
          "owner": "veritas",
          "status": "active",
          "replacement": ""
        }
      ],
      "gate_tier": "T1",
      "gates": ["gate-lint", "gate-test"],
      "pack_cap": {
        "cap": 3,
        "selected": 1,
        "exceeded": false
      }
    }
  },

  "gate_results": [
    {
      "gate_id": "gate-lint",
      "status": "pass",
      "exit_code": 0,
      "duration_ms": 245,
      "log_paths": ["logs/gate-lint.stdout", "logs/gate-lint.stderr"]
    },
    {
      "gate_id": "gate-test",
      "status": "pass",
      "exit_code": 0,
      "duration_ms": 1823,
      "log_paths": ["logs/gate-test.stdout", "logs/gate-test.stderr"]
    }
  ],

  "workspace_delta_paths": ["src/main.py", "tests/test_main.py"],
  "untracked_delta_paths": [],

  "artifact_hashes": [
    {"path": "logs/gate-lint.stdout", "sha256": "abc123..."},
    {"path": "logs/gate-lint.stderr", "sha256": "def456..."}
  ],

  "run_hash": "sha256:789abc...",
  "prev_run_hash": "sha256:456def...",

  "budgets": {
    "tokens": 15000,
    "cost_usd": 0.045,
    "tool_calls": 12
  }
}
```

---

## Canonicalization

When computing `run_hash`:

1. Remove `signature` field from manifest
2. Serialize to JSON using RFC 8785 (JSON Canonicalization Scheme)
3. Compute SHA-256 over the canonical bytes
4. Encode as hex string prefixed with `sha256:`

If RFC 8785 is not available, use deterministic JSON serialization with:
- Sorted keys
- No whitespace
- UTF-8 encoding

**Breaking change rule:** Any change to canonicalization is a breaking change requiring a new schema version.

---

## Verification

A verifier MUST:

1. **Check schema conformance** — manifest matches this specification
2. **Recompute run_hash** — canonicalize manifest, compute SHA-256, compare
3. **Verify artifact hashes** — for each artifact_hash entry, read file, compute SHA-256, compare
4. **Validate signature** (if profile requires) — verify signature over run_hash with key_id
5. **Check reconciliation** — if `untracked_delta_paths` is non-empty, FAIL with `RECON.UNTRACKED_DELTA`

### Verification Outcomes

| Outcome | Reason |
|---------|--------|
| `PASS` | All checks succeeded |
| `FAIL.HASH_MISMATCH` | Computed hash doesn't match `run_hash` |
| `FAIL.ARTIFACT_MISMATCH` | Artifact hash doesn't match computed hash |
| `FAIL.SIGNATURE_INVALID` | Signature verification failed |
| `FAIL.SIGNATURE_REQUIRED` | Profile requires signature but none present |
| `FAIL.RECON.UNTRACKED_DELTA` | Untracked changes detected |

---

## Security Considerations

### Paths Only, No Secrets

Evidence bundles MUST NOT contain:
- API keys, tokens, or credentials
- Raw file contents (use hashes instead)
- Environment variables with sensitive values

Log files in `logs/` should be sanitized to remove any secrets that may have leaked into stdout/stderr.

### Signing Key Management

- Signing keys should be rotated regularly
- `key_id` should be opaque (no embedded key material)
- Key lookup is external to this specification

---

## Compatibility

| Version | Status | Notes |
|---------|--------|-------|
| 1.0.0 | Stable | Initial release |

Backward compatibility:
- New optional fields may be added in minor versions
- Required fields may only change in major versions
- Implementations should ignore unknown fields

---

## Related Specifications

- [Gate Contract](gate-contract.md) — Interface for gates that produce evidence
- [Reconciliation](reconciliation.md) — D ⊆ R scope enforcement
- [Plan Seal](plan-seal.md) — Immutable plan commitment
