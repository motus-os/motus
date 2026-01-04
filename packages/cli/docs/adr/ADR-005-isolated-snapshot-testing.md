# ADR-005: Isolated Snapshot Testing for the UI

## Status
Accepted (retroactive). Implementation planned for v0.1.1.

## Date
2025-12-18 (documented); retroactive to v0.4.x

## Context
UI regression tests are valuable, but “snapshot” style tests are sensitive to:

- Global state (terminal size, focus, input mode)
- Non-deterministic environment differences across machines/CI
- Interference from other tests in the same process

Motus includes Textual snapshot tests for the terminal UI:

- Snapshot tests (planned for v0.1.1, skipped unless `MC_RUN_SNAPSHOTS=1`)
- Test harness notes in `docs/testing.md` explain why snapshots are isolated
- `tests/conftest.py` documents running snapshot tests first to avoid state pollution

Running these snapshots in the main suite by default increases flake and slows down development loops.

## Decision
Keep UI snapshot tests **isolated** from the default test run:

- Default: skip snapshot tests unless explicitly enabled via `MC_RUN_SNAPSHOTS=1`
- Run snapshots as a dedicated suite (locally or in a separate CI job) to keep the main suite fast and reliable
- Prefer deterministic settings (e.g., `PYTHONHASHSEED=0`) when snapshot tests are enabled

## Consequences

### Positive
- Main test suite stays green and fast for everyday development.
- Snapshot suite can be run in a controlled environment to reduce flake and improve signal.
- UI regressions are still catchable when snapshots are intentionally enforced.

### Negative
- Snapshot coverage is not “always on” unless CI is configured to run the snapshot job.
- Requires discipline: contributors must run or update snapshots when intentionally changing UI behavior.

