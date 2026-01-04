# Architecture Decision Records (ADRs)

This directory contains Architecture Decision Records for Motus.

ADRs use a Nygard-style template with:

- Status
- Context
- Decision
- Consequences

## Index (chronological intent)

The `ADR-00x` series documents major early v0.x design decisions retroactively. Dated ADRs document discrete later decisions.

| ADR | Title | Status | Notes |
|-----|-------|--------|-------|
| `ADR-001-textual-framework-choice.md` | Textual Framework for the TUI | Accepted (retroactive) | Terminal UI foundation |
| `ADR-002-tail-based-reading.md` | Tail-Based Reading for Large Session Files | Accepted (retroactive) | Performance default for large JSONL |
| `ADR-003-unified-multi-agent-protocol.md` | Unified Multi-Agent Protocol + Builder Pattern | Accepted (retroactive) | Unifies Claude/Codex/Gemini parsing |
| `ADR-004-dual-interface-tui-web.md` | Dual Interface (Terminal + Web) | Accepted (retroactive) | UI surfaces share orchestrator/protocols |
| `ADR-005-isolated-snapshot-testing.md` | Isolated Snapshot Testing for the UI | Accepted (retroactive) | Keeps main suite fast + green |
| `ADR-2025-12-18-phase-0.1.4-defaults-off.md` | Phase 0.1.4 Enforcement Defaults OFF | Accepted | Benchmarked defaults decision |

