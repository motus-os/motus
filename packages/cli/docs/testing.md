# Testing Strategy (quality-first)

## Commands
- Main suite (fast, stable):  
  `MC_RUN_SNAPSHOTS=0 python3 -m pytest -q -k "not snapshots"`

- Snapshot suite (run isolated):  
  `MC_RUN_SNAPSHOTS=1 python3 -m pytest tests/test_snapshots.py -q`

## Why separate?
- Textual snapshots are sensitive to global state; running them in their own process removes flake.
- Main suite stays green and fast; snapshots remain a strict visual guardrail when intentionally invoked (or in a dedicated CI job).

## CI recommendation
Run two jobs:
1) `MC_RUN_SNAPSHOTS=0 python3 -m pytest -q -k "not snapshots"`
2) `MC_RUN_SNAPSHOTS=1 python3 -m pytest tests/test_snapshots.py -q`

Optional: set `PYTHONHASHSEED=0` in the snapshot job for extra determinism.

Example GitHub Actions (see .github/workflows/ci.yml):
- lint: ruff + black
- tests: main suite with snapshots disabled
- snapshots: isolated run with `MC_RUN_SNAPSHOTS=1` and `PYTHONHASHSEED=0`

## Updating snapshots
When UI changes are intentional:  
`MC_RUN_SNAPSHOTS=1 python3 -m pytest tests/test_snapshots.py --snapshot-update`

Check in the updated SVGs after review.***
