# Testing Strategy

## Commands

Run the full test suite:
```bash
python3 -m pytest tests/ -q
```

Run the fast tier (smoke + critical) in parallel:
```bash
python3 scripts/ci/run_fast_tests.py
```

## CI Recommendation

Run lint and tests in CI:
1. `ruff check src/` - Lint check
2. `python3 -m pytest tests/ -q` - Full test suite

Example GitHub Actions (see .github/workflows/ci.yml):
- lint: ruff + black
- tests: full test suite

## Optional Dependencies

Some tests require optional extras:
- Web tests: install `.[web]`
- MCP tests: install `.[mcp]`
- Gemini tests: install `.[gemini]`

## Snapshot Tests

Snapshot tests require `syrupy` (included in `.[dev]`):

```bash
python -m pytest tests/test_cli_snapshots.py -q
```

For deterministic test runs:
```bash
PYTHONHASHSEED=0 TZ=UTC python -m pytest tests/
```
