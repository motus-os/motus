# ADR-003: Unified Multi-Agent Protocol + Ingestor Pattern

## Status
Accepted (retroactive)

## Date
2025-12-18 (documented); retroactive to v0.2.x

## Context
Motus supports multiple “agent session” sources with different raw formats and conventions:

- Claude Code (JSONL event stream)
- OpenAI Codex CLI (JSONL event stream)
- Gemini CLI (JSON / structured logs)

Without a unifying abstraction, each UI surface would need source-specific parsing, filtering, and rendering logic, multiplying complexity and making it difficult to add a new agent type.

Evidence in the codebase:

- Unified dataclasses:
  - `src/motus/protocols_models.py` (`UnifiedEvent`, `UnifiedSession`)
  - `src/motus/protocols_enums.py` (`Source`, `EventType`, `RiskLevel`, etc.)
- Ingestor pattern:
  - `src/motus/ingestors/base.py` (`BaseBuilder`)
  - `src/motus/ingestors/claude.py`, `codex.py`, `gemini.py`
- Optional validation layer:
  - `src/motus/schema/events.py` (`ParsedEvent`, `unified_to_parsed`)

## Decision
Adopt a **unified protocol** for sessions/events and an **ingestor pattern** for parsing:

- Ingestors parse source-specific raw files into `UnifiedSession` and `UnifiedEvent`.
- Core surfaces (orchestrator, UIs, exporters) operate on unified types.
- A Pydantic schema (`ParsedEvent`) serves as a validation layer where strict correctness is required.

## Consequences

### Positive
- One core data model across the codebase: easier to reason about, test, and evolve.
- Adding a new agent type becomes an additive change: implement a new ingestor and wire it into the orchestrator.
- Shared downstream features (risk detection, health scoring, context aggregation) don’t need per-source implementations.

### Negative
- Requires mapping/normalization from each source into the unified model, which can hide source-specific details unless explicitly preserved in `raw_data`.
- Two layers (dataclasses + Pydantic schema) increase surface area, and the conversion boundary must be tested to avoid drift.
