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
