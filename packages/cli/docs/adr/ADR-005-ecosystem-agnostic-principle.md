# ADR-005: Ecosystem Agnostic Principle

## Status
Accepted

## Date
2026-01-06

## Context

Motus operates in a landscape where multiple AI agent ecosystems exist and are evolving rapidly:

- **Claude** (Anthropic): Projects, artifacts, MCP
- **Codex** (OpenAI): Sessions, snapshots, shell state
- **Gemini** (Google): Context caching, grounding
- **Local agents**: LangChain, AutoGPT, custom implementations

Each ecosystem invests heavily in features that optimize for their specific runtime: session management, context handling, state capture, etc. These are valuable, ecosystem-specific capabilities.

The risk: Motus could either (a) try to compete with these features and lose, or (b) become tightly coupled to one ecosystem and lose portability.

Evidence of ecosystem-agnostic design already in codebase:
- `src/motus/ingestors/claude.py`, `codex.py`, `gemini.py` - unified ingestor pattern
- ADR-003: Unified Multi-Agent Protocol
- Six-call API has no ecosystem-specific parameters

## Decision

**Motus is ecosystem agnostic by design.**

We adopt the "Good Fences" principle: clear boundaries that enable cooperation without competition.

### What Motus Provides (Our Side of the Fence)

| Capability | Description |
|------------|-------------|
| **Receipts** | Structured record of what happened (outcome, evidence, decisions) |
| **Evidence** | Hashes, artifacts, proof bundles |
| **Handoffs** | Cross-agent, cross-session, cross-ecosystem coordination |
| **Audit** | Immutable event stream, queryable history |

### What Ecosystems Provide (Their Side of the Fence)

| Capability | Description |
|------------|-------------|
| **Execution** | Running agent code, tool calls, reasoning |
| **Session management** | Context windows, continuation, snapshots |
| **Ecosystem features** | Projects (Claude), shell state (Codex), grounding (Gemini) |

### Boundary Contract

```
┌─────────────────────────────────────────────────────────────┐
│                     ECOSYSTEM LAYER                         │
│  Claude │ Codex │ Gemini │ LangChain │ Custom │ ...        │
│         │       │        │           │        │            │
│  (own snapshots, sessions, context, execution)             │
└────────────────────────┬────────────────────────────────────┘
                         │
                    INGEST (read-only)
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                      MOTUS LAYER                            │
│                                                             │
│  Receipts │ Evidence │ Handoffs │ Audit │ Coordination     │
│                                                             │
│  (accountability, provability, multi-agent orchestration)  │
└─────────────────────────────────────────────────────────────┘
```

### The One-Liner

> "Codex knows what Codex did. Claude knows what Claude did. **Motus knows what everyone did.**"

## Consequences

### Positive

- **No ecosystem lock-in**: Users can switch agents without losing history
- **Complementary, not competitive**: Ecosystem features make Motus more valuable, not less
- **Clear scope**: Contributors know what to build (accountability) vs what not to build (execution)
- **Interop opportunity**: As ecosystems add state capture, Motus can ingest and unify

### Negative

- **Dependency on ecosystems**: If an ecosystem changes format, ingestors must update
- **Feature pressure**: Users may ask for ecosystem-specific features that violate the principle
- **Positioning challenge**: Must clearly communicate "layer on top" vs "replacement"

### Guardrails

1. **No ecosystem-specific code in core kernel** - only in ingestors
2. **Ingestors are read-only** - Motus observes, doesn't control ecosystem behavior
3. **Receipt schema is ecosystem-agnostic** - no Claude-specific or Codex-specific fields in core
4. **New ecosystem = new ingestor** - additive change, not core change

## Related

- ADR-003: Unified Multi-Agent Protocol (implementation pattern)
- ARCHITECTURE.md: Local-First Sovereignty (complementary principle)
- `src/motus/ingestors/` (reference implementation)
