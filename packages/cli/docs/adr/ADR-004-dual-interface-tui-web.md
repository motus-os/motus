# ADR-004: Dual Interface (Terminal + Web)

## Status
Accepted (retroactive)

## Date
2025-12-18 (documented); retroactive to v0.3.x

## Context
Motus Command is used in two primary modes:

1. **Local developer workflow**: a fast terminal experience that can be run anywhere.
2. **Dashboards / collaboration**: a browser surface that is easier to share, extend, and integrate.

A single UI surface would not serve both modes equally well, and UI code tends to attract product pressure quickly. To avoid coupling product iteration to parsing and data modeling, Motus needs an explicit boundary between:

- Core session discovery/parsing (ingestors + orchestrator)
- Presentation surfaces (TUI, web)

Evidence in the repository:

- Web UI implementation and server:
  - `src/motus/ui/web/*` (FastAPI + WebSocket handlers)
  - `pyproject.toml` includes `fastapi` and `websockets`
  - CLI exposes web surface (`mc web`) per `README.md`
- Terminal UI implementation (historical / retained in repo):
  - `src/motus/ui/tui/*` (Textual-based TUI)

## Decision
Support **both** a terminal surface and a web surface, sharing the same core orchestrator and protocols:

- The **orchestrator** remains the “composition root” for session discovery and event loading.
- UI surfaces depend on the orchestrator, not on source-specific parsing.
- The web UI uses a FastAPI server and WebSockets for incremental updates.

## Consequences

### Positive
- Users can choose the surface that fits their workflow (terminal-first or browser-first).
- The core model (protocols/orchestrator) stays reusable and testable independent of UI choices.
- Enables future integrations (exporters, CI views) without rewriting parsing logic.

### Negative
- Two surfaces increase maintenance: duplication in UI rendering logic, more testing burden, and more places for subtle UX drift.
- UI frameworks can impose global state constraints (notably for Textual), which impacts test strategy.

### Notes / Evolution
The web UI is currently treated as the primary interface (see `src/motus/ui/__init__.py`). This ADR documents the architectural intent: core logic remains UI-agnostic, allowing the “primary” surface to evolve over time.
