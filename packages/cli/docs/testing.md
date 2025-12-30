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

## Snapshot Testing

Snapshot testing for the TUI is planned for v0.1.1. Not yet available.

When implemented, snapshots will:
- Run isolated from the main suite via `MC_RUN_SNAPSHOTS=1`
- Use `PYTHONHASHSEED=0` for determinism
- Provide visual regression coverage for UI changes
