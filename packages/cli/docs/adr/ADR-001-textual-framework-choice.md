# ADR-001: Textual Framework for the TUI

## Status
Accepted (retroactive)

## Date
2025-12-18 (documented); retroactive to early v0.x

## Context
Motus started as a terminal-first dashboard for observing agent sessions (Claude/Codex/Gemini). The UI needed:

- A real layout system (panels, lists, overlays)
- Keyboard navigation with predictable focus behavior
- A path to deterministic “visual regression” testing

Alternatives included:

- A hand-rolled Rich-based console UI (faster to start, but limited layout/state management)
- A full web UI only (more accessible, but slower to stand up and harder to run offline)

Evidence in the repository shows Textual was chosen and used to implement the TUI:

- Dependency: `pyproject.toml` includes `textual>=6.0.0`
- TUI implementation: `src/motus/ui/tui/app.py`, `src/motus/ui/tui/panels/*`
- Snapshot tests: Planned for v0.1.1 (not yet implemented)

## Decision
Use **Textual** as the framework for the terminal UI (TUI).

The architecture keeps the **orchestrator + protocols** independent of UI so alternative surfaces (web, future UIs) can reuse the same core logic.

## Consequences

### Positive
- A full-featured terminal UI with a composable widget model and event loop.
- A viable snapshot-testing strategy (planned for v0.1.1) to prevent silent UI regressions.

### Negative
- Textual introduces global/process-level state concerns that can leak between tests and runs; this later motivated isolating snapshot tests behind an env flag (see `docs/testing.md`).
- Additional dependency weight and framework constraints compared to Rich-only approaches.

### Notes / Evolution
This ADR documents the **original** TUI choice. Subsequent work shifted toward a web-first surface; the repo currently notes: “The Textual-based TUI was removed in v0.5.0. The Web UI is the primary interface.” (`src/motus/ui/__init__.py`). The TUI code and its tests remain a useful reference point for earlier design constraints and regression coverage.

