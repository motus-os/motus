# Motus Feature Matrix

**Last Updated**: 2025-12-26
**Purpose**: Track feature support across Claude, Codex, and Gemini

---

## Parsing Features

| Feature | Claude | Codex | Gemini | Notes |
|---------|:------:|:-----:|:------:|-------|
| Session discovery | ✓ | ✓ | ✓ | All agents supported |
| User messages | ✓ | ✓ | ✓ | |
| Assistant responses | ✓ | ✓ | ✓ | |
| Tool calls | ✓ | ✓ | ✓ | |
| Tool results | ✓ | ✓ | ✓ | |
| Thinking blocks | ✓ | ✓ | ✓ | Extended thinking |
| Error events | ✓ | ⚠️ | ⚠️ | Partial coverage |
| File operations | ✓ | ✓ | ✓ | Read/Write/Edit tracking |
| Agent spawn | ✓ | ✓ | ✓ | Subagent detection |

## Context Injection (Hooks)

| Feature | Claude | Codex | Gemini | Notes |
|---------|:------:|:-----:|:------:|-------|
| SessionStart hook | ✓ | N/A | N/A | Claude only has hook API |
| UserPromptSubmit hook | ✓ | N/A | N/A | |
| Context injection | ✓ | ✗ | ✗ | Codex/Gemini lack hook mechanism |

## Decision Extraction

| Feature | Claude | Codex | Gemini | Notes |
|---------|:------:|:-----:|:------:|-------|
| Decision detection | ✓ | ✓ | ✓ | From thinking blocks |
| File change tracking | ✓ | ✓ | ✓ | |
| Hot files analysis | ✓ | ✓ | ✓ | |
| Cross-session context | ✓ | ✓ | ✓ | |

## Format Compatibility

| Feature | Claude | Codex | Gemini | Notes |
|---------|:------:|:-----:|:------:|-------|
| Version captured | ✓ | ✓ | ✗ | Gemini has no version |
| Version validated | ✗ | ✗ | ✗ | **GAP** - not implemented |
| Format change alerts | ✗ | ✗ | ✗ | **GAP** - not implemented |
| Official docs | ✗ | ✓ | ✗ | Only Codex has docs |

## Platform Support

| Platform | Status | Notes |
|----------|:------:|-------|
| macOS (Intel) | ✓ | Tested |
| macOS (Apple Silicon) | ✓ | Primary dev platform |
| Linux (x86_64) | ✓ | CI tested |
| Linux (ARM64) | ⚠️ | Untested |
| Windows (WSL) | ⚠️ | Untested |
| Windows (native) | ✗ | Not supported |

## Legend

- ✓ = Fully supported
- ⚠️ = Partial/untested
- ✗ = Not supported
- N/A = Not applicable (feature doesn't exist upstream)

---

## Update Triggers

This document must be updated when:
- New event type added to any parser
- New agent added
- Platform support changes
- Hook mechanism added to Codex/Gemini

**Trigger file**: `src/motus/ingestors/*.py`
