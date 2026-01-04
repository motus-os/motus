# Motus 0.2.2 - Feature Parity Roadmap

## Executive Summary

**Primary Goal**: Full feature parity across CLI, TUI, and Web for all sources (Claude, Codex, Gemini, SDK traces).

**Current State**: Web and TUI are largely source-aware; CLI mission_control is the main gap (hides Codex/Gemini).

---

## Critical Fixes (Must Have for 0.2.2)

### 1. CLI Mission Control Shows All Sources
**Problem**: `mission_control` filters to `status == "active"` only. Codex/Gemini are created with `status="orphaned"`, so their events never appear.

**Fix Options**:
- A) Mark recent non-Claude sessions as `active`/`open` based on mtime (< 5 min = active)
- B) Include `open`/`orphaned` in the feed for recent sessions
- C) Add `--all-sources` flag to mission_control

**Files**: `src/motus/commands/mission_control_cmd.py`, `src/motus/session_manager.py`

### 2. Context Extraction Across Sources
**Problem**: Decision/file extraction may be Claude-biased (pattern-matches "I'll...", "I decided..." in thinking blocks).

**Fix**:
- Extend decision detection to Codex/Gemini response text
- Map Gemini `thoughts`/`reasoning` fields to thinking events
- Include Codex tool descriptions as pseudo-thinking

**Files**: `src/motus/hooks.py`, `src/motus/gemini_parser.py`, `src/motus/codex_parser.py`

### 3. Unified Status Assignment
**Problem**: Claude uses process detection for status; Codex/Gemini always marked orphaned.

**Fix**: Use mtime-based status for all sources:
- mtime < 2 min → `active`
- mtime < 30 min → `open`
- mtime >= 30 min → `orphaned`

**Files**: `src/motus/session_manager.py`

---

## Feature Additions (Should Have)

### 4. CLI Health/Insight Block
**Problem**: Web has health/intent/working-memory widgets; CLI has only raw feed.

**Add to CLI**:
```
╭─ Session Health ─────────────────────────╮
│ Health: 85% (On Track)                   │
│ Tool Calls: 12 | Decisions: 3            │
│ Files Modified: 5 | Risk Ops: 1          │
│ Last Activity: 2 min ago                 │
╰──────────────────────────────────────────╯
```

**Files**: `src/motus/commands/mission_control_cmd.py`

### 5. Thinking Surrogates for Codex/Gemini
**Problem**: Codex doesn't emit thinking blocks. Chain-of-thought visibility is Claude-only.

**Fix**: Inject synthetic thinking events:
- Before tool calls: `"Planning: {tool_name} with {args_summary}..."`
- After model responses: Extract reasoning patterns from response text

**Files**: `src/motus/codex_parser.py`, `src/motus/gemini_parser.py`

### 6. CLI Backfill Flag
**Problem**: Web backfills recent events on connect; CLI starts fresh.

**Add**: `motus mission-control --backfill 10` to show last N events per session.

**Files**: `src/motus/commands/mission_control_cmd.py`

---

## Cleanup (Nice to Have)

### 7. Consolidate Discovery Paths
**Problem**: Multiple discovery paths (`find_claude_sessions`, `SessionManager.find_sessions`, per-source finders).

**Fix**: Single `SessionManager.discover_all()` entry point that all surfaces use.

### 8. Remove Legacy Aliases
- Remove any lingering "loom" references
- Consolidate to single `~/.mc` state directory
- Remove dual path references

### 9. Simplify Config
- Single `RiskConfig` source of truth
- Remove local constants in cli/utils
- Drop unused retention knobs (document as "user-managed")

### 10. Clean UI Assets
- Remove unused CSS/JS fragments
- Ensure single `escapeHtml` path
- Remove redundant template variants

---

## Testing Requirements

### New Tests Needed
1. `test_mission_control_shows_codex_gemini` - Verify non-Claude sessions appear
2. `test_status_assignment_by_mtime` - Verify consistent status across sources
3. `test_decision_extraction_codex` - Verify decisions from Codex responses
4. `test_decision_extraction_gemini` - Verify decisions from Gemini responses
5. `test_thinking_surrogates` - Verify synthetic thinking events

### Existing Tests
- 379 passing locally
- CI environment-specific failures (continue-on-error for now)

---

## Implementation Order

### Phase 1: Critical Path (Day 1)
1. Fix status assignment for Codex/Gemini based on mtime
2. Update mission_control to show recent sessions regardless of source
3. Verify context extraction includes all sources

### Phase 2: Enrichment (Day 2)
4. Add CLI health/insight block
5. Implement thinking surrogates for Codex/Gemini
6. Add backfill flag to mission_control

### Phase 3: Cleanup (Day 3)
7. Consolidate discovery paths
8. Remove legacy aliases
9. Clean unused code/assets
10. Update documentation

---

## Version Bump Checklist

- [ ] All critical fixes implemented
- [ ] New tests added and passing
- [ ] pyproject.toml version → 0.2.2
- [ ] CHANGELOG updated
- [ ] README updated with new features
- [ ] CI passing (or understood environment-specific issues)

---

## Notes

### Security Posture
- Local-only binding (127.0.0.1) is intentional
- No auth needed for loopback
- If remote access ever needed, add auth first

### CoT Limitations
- Claude: Full thinking visibility
- Codex: Tool-focused, limited reasoning visible
- Gemini: Variable; depends on model output

### Retention
- User-managed (no enforced defaults)
- Document recommended pruning in README
