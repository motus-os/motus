# Testing Strategy

## Commands

Run the full test suite:
```bash
python3 -m pytest tests/ -q
```

## CI Recommendation

Run lint and tests in CI:
1. `ruff check src/` - Lint check
2. `python3 -m pytest tests/ -q` - Full test suite

Example GitHub Actions (see .github/workflows/ci.yml):
- lint: ruff + black
- tests: full test suite

## Snapshot Tests

Snapshot testing is planned for a future release. The current test suite uses:

```bash
python -m pytest tests/ -q
```

For deterministic test runs:
```bash
PYTHONHASHSEED=0 TZ=UTC python -m pytest tests/
```
