# Health Ledger

The Health Ledger is the canonical, auditable record of Motus codebase health.
It produces a JSON artifact on every run and enforces regression gates against
a committed baseline.

## What It Measures

- **Correctness**: test pass/fail counts + runtime
- **Security**: `pip-audit` HIGH/CRITICAL deltas
- **Performance**: `policy_run` P95 latency
- **Coverage**: overall + core module coverage
- **Lint/Type**: ruff + mypy error counts

## Policy

Policy thresholds live in:

- `docs/quality/health-policy.json`

Baseline metrics live in:

- `docs/quality/health-baseline.json`

## How To Run

From `packages/cli`:

```bash
python scripts/ci/health_ledger.py --output artifacts/health.json
```

To update the baseline (manual, explicit):

```bash
python scripts/ci/health_ledger.py --write-baseline
```

## Notes

- The health ledger runs a deterministic `policy run` against test fixtures
  to populate policy performance metrics.
- `.mc` state paths are preserved for compatibility; the ledger only enforces
  health, not state directory naming.

## Latest Review

**Date**: 2026-01-05

**Status**: PASS

**Summary**:
- Tests: 1947 passed, 4 skipped
- Coverage: Core modules meet policy thresholds
- Security: No critical vulnerabilities in core dependencies
- Lint: Clean (ruff, mypy)

**Non-Core Vulnerabilities** (dev dependencies, not blocking):
- ansible 7.2.0: CVE-2023-5115, CVE-2025-14010
- ansible-core 2.14.2: Multiple CVEs (dev tooling only)
- cbor2 5.7.1: CVE-2025-68131 (decoder state issue)
