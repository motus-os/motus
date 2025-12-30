# Motus Command 0.2.2 - Architectural Plan

## Philosophy: Builder Pattern with Protocol-Based Design

**Stop patching. Start building.**

The current codebase has grown organically with Claude-first assumptions baked into multiple layers. Rather than continuing to patch each layer, we will:

1. Define **clear protocols (interfaces)** that all sources must implement
2. Create **source-specific builders** that produce unified data structures
3. Use **composition** - surfaces (CLI/TUI/Web) consume unified data, don't know about sources
4. **Single path** - one discovery, one status assignment, one event extraction

---

## Current Architecture (Problems)

```
┌─────────────────────────────────────────────────────────────────┐
│                     CURRENT (Tangled)                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  CLI ──────┬──> session_manager._find_claude_sessions()         │
│            ├──> session_manager._find_codex_sessions()          │
│            └──> session_manager._find_gemini_sessions()         │
│                      │                                          │
│                      ├── Claude: process detection → status     │
│                      ├── Codex: always "orphaned" ❌            │
│                      └── Gemini: always "orphaned" ❌           │
│                                                                 │
│  TUI ──────┬──> transcript_parser (Claude-only thinking)        │
│            └──> codex_parser / gemini_parser (separate logic)   │
│                                                                 │
│  Web ──────┬──> hooks.py (Claude event patterns)                │
│            └──> separate Codex/Gemini handlers                  │
│                                                                 │
│  mission_control ──> filters status == "active" only ❌         │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Problems:**
- Status assignment differs by source
- Event extraction differs by source
- CLI mission_control filters out non-Claude by accident
- 3+ discovery paths, 3+ parsers, no unified interface

---

## Target Architecture (Clean)

```
┌─────────────────────────────────────────────────────────────────┐
│                     TARGET (Layered)                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │                    SURFACES (Consumers)                     ││
│  │  CLI mission_control  │  TUI  │  Web Dashboard              ││
│  │         ↓                ↓           ↓                      ││
│  │    UnifiedSession    UnifiedEvent   SessionHealth           ││
│  └─────────────────────────────────────────────────────────────┘│
│                            ↑                                    │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │                    CORE (Orchestrator)                      ││
│  │                                                             ││
│  │  SessionOrchestrator                                        ││
│  │    .discover_all() → List[UnifiedSession]                   ││
│  │    .get_events(session) → List[UnifiedEvent]                ││
│  │    .get_health(session) → SessionHealth                     ││
│  │                                                             ││
│  └─────────────────────────────────────────────────────────────┘│
│                            ↑                                    │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │                    BUILDERS (Adapters)                      ││
│  │                                                             ││
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐        ││
│  │  │ ClaudeBuilder│ │ CodexBuilder │ │ GeminiBuilder│        ││
│  │  │              │ │              │ │              │        ││
│  │  │ discover()   │ │ discover()   │ │ discover()   │        ││
│  │  │ parse()      │ │ parse()      │ │ parse()      │        ││
│  │  │ status()     │ │ status()     │ │ status()     │        ││
│  │  └──────────────┘ └──────────────┘ └──────────────┘        ││
│  │                                                             ││
│  │  ┌──────────────┐                                          ││
│  │  │ SDKBuilder   │  (for Tracer SDK sessions)               ││
│  │  └──────────────┘                                          ││
│  │                                                             ││
│  └─────────────────────────────────────────────────────────────┘│
│                            ↑                                    │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │                    PROTOCOLS (Contracts)                    ││
│  │                                                             ││
│  │  class SessionBuilder(Protocol):                            ││
│  │      def discover(max_age_hours) -> List[RawSession]        ││
│  │      def parse_events(path) -> List[UnifiedEvent]           ││
│  │      def compute_status(session, now) -> SessionStatus      ││
│  │                                                             ││
│  │  @dataclass UnifiedSession                                  ││
│  │  @dataclass UnifiedEvent                                    ││
│  │  @dataclass SessionHealth                                   ││
│  │  @dataclass SessionStatus                                   ││
│  │                                                             ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Core Data Structures

### 1. UnifiedSession

```python
@dataclass
class UnifiedSession:
    """Source-agnostic session representation."""
    session_id: str
    source: Literal["claude", "codex", "gemini", "sdk"]
    file_path: Path
    project_path: str

    # Timing
    created_at: datetime
    last_modified: datetime

    # Status (computed uniformly)
    status: Literal["active", "open", "idle", "orphaned", "crashed"]
    status_reason: str  # Why this status was assigned

    # Metrics (for health widget)
    event_count: int
    tool_count: int
    decision_count: int
    file_change_count: int
    thinking_count: int

    # Context
    last_action: str
    working_on: str  # Extracted intent/goal
```

### 2. UnifiedEvent

```python
@dataclass
class UnifiedEvent:
    """Source-agnostic event representation."""
    event_id: str
    session_id: str
    timestamp: datetime

    # Type hierarchy
    event_type: Literal["thinking", "tool", "decision", "file_change", "agent_spawn", "error"]

    # Common fields
    content: str  # Human-readable summary
    raw_data: dict  # Original source data for debugging

    # Type-specific (optional)
    tool_name: Optional[str] = None
    tool_input: Optional[dict] = None
    tool_output: Optional[str] = None
    tool_status: Optional[str] = None
    risk_level: Optional[str] = None
    file_path: Optional[str] = None
    decision_text: Optional[str] = None
    reasoning: Optional[str] = None
```

### 3. SessionHealth

```python
@dataclass
class SessionHealth:
    """Health metrics for a session (powers CLI/Web widgets)."""
    session_id: str

    # Overall health score (0-100)
    health_score: int
    health_label: Literal["On Track", "Needs Attention", "At Risk", "Stalled"]

    # Activity metrics
    tool_calls: int
    decisions: int
    files_modified: int
    risky_operations: int
    thinking_blocks: int

    # Timing
    duration_seconds: int
    last_activity_seconds: int

    # Intent (extracted from context)
    current_goal: str
    working_memory: List[str]  # Recent files/decisions
```

---

## Builder Protocol

```python
from typing import Protocol, List
from pathlib import Path
from datetime import datetime

class SessionBuilder(Protocol):
    """Protocol that all source builders must implement."""

    @property
    def source_name(self) -> str:
        """Return source identifier: 'claude', 'codex', 'gemini', 'sdk'"""
        ...

    def discover(self, max_age_hours: int = 24) -> List[RawSession]:
        """Find all sessions from this source within age limit."""
        ...

    def parse_events(self, file_path: Path) -> List[UnifiedEvent]:
        """Parse transcript file into unified events."""
        ...

    def compute_status(
        self,
        file_path: Path,
        last_modified: datetime,
        now: datetime
    ) -> tuple[str, str]:
        """
        Compute status and reason.
        Returns: (status, reason)

        Status assignment rules (UNIFORM for all sources):
        - active: modified < 2 min ago
        - open: modified < 30 min ago
        - idle: modified < 2 hours ago
        - orphaned: modified >= 2 hours ago
        - crashed: was doing risky op when stopped (1-5 min, no completion marker)
        """
        ...

    def extract_thinking(self, file_path: Path) -> List[UnifiedEvent]:
        """
        Extract thinking/reasoning events.

        For Claude: actual thinking blocks
        For Codex: synthetic from tool planning + response patterns
        For Gemini: thoughts/reasoning fields
        """
        ...

    def extract_decisions(self, file_path: Path) -> List[UnifiedEvent]:
        """
        Extract decision events from any source.

        Patterns to match (source-agnostic):
        - "I'll...", "I decided...", "I'm going to..."
        - "Let me...", "Planning to..."
        - Tool selections with reasoning
        """
        ...
```

---

## Implementation Plan

### Phase 1: Foundation (New Files)

**Files to create:**

```
src/motus/
├── protocols.py          # UnifiedSession, UnifiedEvent, SessionHealth, SessionBuilder
├── orchestrator.py       # SessionOrchestrator - single entry point
└── builders/
    ├── __init__.py
    ├── base.py           # BaseBuilder with shared mtime-based status logic
    ├── claude.py         # ClaudeBuilder
    ├── codex.py          # CodexBuilder
    ├── gemini.py         # GeminiBuilder
    └── sdk.py            # SDKBuilder (for Tracer sessions)
```

**Key principle:** These are NEW files. We don't modify existing code yet. Build the new system alongside the old.

### Phase 2: Builder Implementation

Each builder implements the protocol. Example structure:

```python
# builders/base.py
class BaseBuilder:
    """Shared logic for all builders."""

    def compute_status(self, file_path, last_modified, now) -> tuple[str, str]:
        """Unified mtime-based status (same for ALL sources)."""
        age_seconds = (now - last_modified).total_seconds()

        if age_seconds < 120:  # 2 min
            return ("active", "Modified within 2 minutes")
        elif age_seconds < 1800:  # 30 min
            return ("open", "Modified within 30 minutes")
        elif age_seconds < 7200:  # 2 hours
            return ("idle", "Modified within 2 hours")
        else:
            return ("orphaned", "No recent activity")

    def check_crashed(self, file_path, last_modified, now, source) -> tuple[str, str] | None:
        """Check if session crashed during risky operation."""
        age_seconds = (now - last_modified).total_seconds()

        # Only check 1-5 minute old sessions
        if not (60 < age_seconds < 300):
            return None

        last_action = self._get_last_action(file_path, source)
        if last_action and any(k in last_action for k in ("Edit", "Write", "Bash")):
            if not self._has_completion_marker(file_path, source):
                return ("crashed", f"Stopped during: {last_action}")

        return None

# builders/claude.py
class ClaudeBuilder(BaseBuilder):
    source_name = "claude"

    def discover(self, max_age_hours: int = 24) -> List[RawSession]:
        """Find Claude sessions in ~/.claude/projects/"""
        ...

    def parse_events(self, file_path: Path) -> List[UnifiedEvent]:
        """Parse Claude JSONL transcript."""
        ...

    def extract_thinking(self, file_path: Path) -> List[UnifiedEvent]:
        """Extract actual thinking blocks from Claude transcripts."""
        ...

# builders/codex.py
class CodexBuilder(BaseBuilder):
    source_name = "codex"

    def extract_thinking(self, file_path: Path) -> List[UnifiedEvent]:
        """
        Generate SYNTHETIC thinking for Codex.

        Since Codex doesn't emit thinking blocks, we create surrogates:
        1. Before tool calls: "Planning: {tool_name} with {args_summary}..."
        2. From response patterns: Extract reasoning from model text
        """
        ...
```

### Phase 3: Orchestrator

```python
# orchestrator.py
class SessionOrchestrator:
    """Single entry point for all session operations."""

    def __init__(self):
        self.builders = [
            ClaudeBuilder(),
            CodexBuilder(),
            GeminiBuilder(),
            SDKBuilder(),
        ]

    def discover_all(self, max_age_hours: int = 24) -> List[UnifiedSession]:
        """Discover sessions from ALL sources."""
        sessions = []
        now = datetime.now()

        for builder in self.builders:
            try:
                raw_sessions = builder.discover(max_age_hours)
                for raw in raw_sessions:
                    # Uniform status assignment
                    status, reason = builder.compute_status(
                        raw.file_path, raw.last_modified, now
                    )
                    # Check for crash override
                    crash = builder.check_crashed(
                        raw.file_path, raw.last_modified, now, builder.source_name
                    )
                    if crash:
                        status, reason = crash

                    sessions.append(UnifiedSession(
                        session_id=raw.session_id,
                        source=builder.source_name,
                        status=status,
                        status_reason=reason,
                        ...
                    ))
            except Exception as e:
                logger.warning(f"Builder {builder.source_name} failed: {e}")

        return sorted(sessions, key=lambda s: (STATUS_ORDER[s.status], -s.last_modified.timestamp()))

    def get_events(self, session: UnifiedSession, limit: int = 100) -> List[UnifiedEvent]:
        """Get unified events for a session."""
        builder = self._get_builder(session.source)
        return builder.parse_events(session.file_path)[:limit]

    def get_health(self, session: UnifiedSession) -> SessionHealth:
        """Compute health metrics for a session."""
        events = self.get_events(session, limit=500)
        ...
```

### Phase 4: Surface Migration

**Migrate surfaces one at a time:**

1. **CLI mission_control** - Switch to `orchestrator.discover_all()`
2. **TUI** - Switch to `orchestrator.get_events()`
3. **Web** - Switch to orchestrator for sessions and events

**Key:** Each surface migration is independent. We can ship incrementally.

### Phase 5: Cleanup

Once all surfaces use the orchestrator:

1. Delete old `_find_claude_sessions`, `_find_codex_sessions`, etc.
2. Delete redundant parser code
3. Consolidate to single discovery path
4. Remove legacy "loom" references

---

## Sub-Agent Implementation Tasks

Each builder can be implemented by a focused sub-agent:

### Agent 1: Protocol Designer
- Create `protocols.py` with all data structures
- Define clear interfaces
- Add comprehensive docstrings
- Write unit tests for data structures

### Agent 2: Claude Builder
- Implement `ClaudeBuilder` class
- Migrate existing Claude parsing logic
- Ensure thinking block extraction works
- Unit tests

### Agent 3: Codex Builder
- Implement `CodexBuilder` class
- Implement synthetic thinking generation
- Decision extraction from response text
- Unit tests

### Agent 4: Gemini Builder
- Implement `GeminiBuilder` class
- Map thoughts/reasoning to thinking events
- Handle JSON format differences
- Unit tests

### Agent 5: SDK Builder
- Implement `SDKBuilder` for Tracer sessions
- Parse JSONL trace files
- Unit tests

### Agent 6: Orchestrator
- Implement `SessionOrchestrator`
- Wire up all builders
- Integration tests

### Agent 7: CLI Migration
- Update mission_control to use orchestrator
- Add health widget to CLI
- Add backfill flag

### Agent 8: TUI/Web Migration
- Update TUI to use orchestrator
- Update Web to use orchestrator
- Verify feature parity

---

## Success Criteria

### Must Have (0.2.2 Release)
- [ ] All sources appear in `mc mission-control` (not just Claude)
- [ ] Status assignment is uniform (mtime-based for all)
- [ ] CLI shows session health widget
- [ ] 379+ tests passing

### Should Have
- [ ] Thinking surrogates for Codex/Gemini
- [ ] Decision extraction from all sources
- [ ] Backfill flag for mission_control

### Nice to Have
- [ ] Legacy code removed
- [ ] Single discovery path
- [ ] Documentation updated

---

## Testing Strategy

```
tests/
├── unit/
│   ├── test_protocols.py        # Data structure validation
│   ├── test_claude_builder.py   # Claude-specific parsing
│   ├── test_codex_builder.py    # Codex-specific parsing
│   ├── test_gemini_builder.py   # Gemini-specific parsing
│   └── test_orchestrator.py     # Integration of builders
├── integration/
│   ├── test_cli_mission_control.py  # End-to-end CLI
│   └── test_web_sessions.py         # End-to-end Web
└── fixtures/
    ├── claude_transcript.jsonl
    ├── codex_session.jsonl
    └── gemini_session.json
```

---

## Version Bump Checklist

- [ ] `protocols.py` created and tested
- [ ] All 4 builders implemented and tested
- [ ] `SessionOrchestrator` wired up
- [ ] CLI mission_control migrated
- [ ] All sources visible in mission_control
- [ ] pyproject.toml version → 0.2.2
- [ ] CHANGELOG updated
- [ ] CI passing

---

## Notes

### Why Builder Pattern?
- **Isolation:** Each source's quirks are contained in its builder
- **Testability:** Can test each builder independently
- **Extensibility:** Adding a new source = adding a new builder
- **Clarity:** Surfaces don't know about source-specific details

### Why Not Patch?
- Current code has assumptions baked in at multiple layers
- Patching creates more technical debt
- Clean interfaces enable future features (multi-agent trees, etc.)
- Builder pattern scales better

### Risk Mitigation
- Build new system alongside old (no breaking changes)
- Migrate surfaces one at a time
- Feature flags if needed
- Comprehensive test coverage before migration

---

## v0.3 Features Rolled Into 0.2.2

The following features from `ROADMAP-v0.3.md` are pulled forward into 0.2.2 because they fit naturally with the builder architecture:

### 1. Decision Ledger (v0.3 2.1) → UnifiedEvent.decision_text + reasoning

**Original v0.3 spec:**
```json
{
  "decisions": [
    {
      "timestamp": "2025-12-01T10:30:00Z",
      "decision": "Use SessionManager instead of find_claude_sessions",
      "reasoning": "SessionManager includes Codex sessions",
      "files_affected": ["cli.py"],
      "reversible": true
    }
  ]
}
```

**0.2.2 implementation:** Built into `UnifiedEvent` with `event_type="decision"`:
- `decision_text` - the decision made
- `reasoning` - why this decision was made
- `file_path` - files affected (optional)
- Extracted by each builder's `extract_decisions()` method

### 2. Extended Event Metadata (v0.3 EnrichedEvent) → UnifiedEvent

**Pulled forward fields:**
```python
@dataclass
class UnifiedEvent:
    # ... existing fields ...

    # From v0.3 EnrichedEvent
    model: Optional[str] = None          # Which model generated this
    tokens_used: Optional[int] = None    # Token consumption
    tool_latency_ms: Optional[int] = None # Tool execution time
    cache_hit: Optional[bool] = None     # Was response cached
```

**NOT pulled forward (stay in v0.3):**
- `intent_alignment: float` - requires Intent Spine feature
- `git_context: GitContext` - requires checkpoint system

### 3. Session Handoff (v0.3 2.4) → SessionOrchestrator.export_handoff()

**0.2.2 implementation:** Basic handoff export method:
```python
class SessionOrchestrator:
    def export_handoff(self, session: UnifiedSession, format: str = "markdown") -> str:
        """
        Generate portable session summary for cross-agent handoff.

        Formats: "markdown" (for CLAUDE.md), "json" (for programmatic use)

        Includes:
        - Session summary (source, duration, status)
        - Decisions made with reasoning
        - Files modified
        - Current working state
        - Pending TODOs (if detectable)
        """
```

**NOT pulled forward (stay in v0.3):**
- `mc handoff --to codex` format conversion - future work
- Interactive handoff prompts

### 4. File Touch Tracking (v0.3 SessionMetadata.file_touches) → UnifiedSession

**0.2.2 implementation:** Track files read/modified per session:
```python
@dataclass
class UnifiedSession:
    # ... existing fields ...

    # From v0.3 SessionMetadata
    files_read: List[str] = field(default_factory=list)
    files_modified: List[str] = field(default_factory=list)
```

**Why this enables v0.3:**
- Conflict Radar (v0.3 2.2) needs file touch tracking
- Scope Creep Monitor (v0.3 1.4) needs file touch tracking
- We build the foundation now, features come in v0.3

---

## Features Explicitly NOT in 0.2.2 (Stay in v0.3)

| Feature | Reason to Defer |
|---------|-----------------|
| Intent Spine | Separate subsystem, needs design |
| State Checkpoints | Git wrapper, separate feature |
| Test Harness Detection | Separate feature |
| Scope Creep Monitor | Needs Intent Spine first |
| Conflict Radar | Needs file touch tracking first (0.2.2 builds foundation) |
| Policy Packs | Separate config system |
| Incident Co-pilot | Needs cross-session memory |
| Cross-session Memory | Needs SQLite, bigger effort |
| Dry Run Mode | Separate feature |

---

## Updated Data Structures (with v0.3 fields)

### UnifiedSession (Final)

```python
@dataclass
class UnifiedSession:
    """Source-agnostic session representation."""
    # Identity
    session_id: str
    source: Literal["claude", "codex", "gemini", "sdk"]
    file_path: Path
    project_path: str

    # Timing
    created_at: datetime
    last_modified: datetime

    # Status (computed uniformly)
    status: Literal["active", "open", "idle", "orphaned", "crashed"]
    status_reason: str

    # Metrics
    event_count: int = 0
    tool_count: int = 0
    decision_count: int = 0
    file_change_count: int = 0
    thinking_count: int = 0

    # Context
    last_action: str = ""
    working_on: str = ""

    # v0.3 forward-ported: File tracking (enables Conflict Radar, Scope Creep)
    files_read: List[str] = field(default_factory=list)
    files_modified: List[str] = field(default_factory=list)
```

### UnifiedEvent (Final)

```python
@dataclass
class UnifiedEvent:
    """Source-agnostic event representation."""
    # Identity
    event_id: str
    session_id: str
    timestamp: datetime

    # Type
    event_type: Literal["thinking", "tool", "decision", "file_change", "agent_spawn", "error"]

    # Common
    content: str
    raw_data: dict = field(default_factory=dict)

    # Tool-specific
    tool_name: Optional[str] = None
    tool_input: Optional[dict] = None
    tool_output: Optional[str] = None
    tool_status: Optional[Literal["success", "error", "pending"]] = None
    risk_level: Optional[Literal["safe", "medium", "high", "critical"]] = None

    # Decision-specific (v0.3 Decision Ledger)
    decision_text: Optional[str] = None
    reasoning: Optional[str] = None
    files_affected: List[str] = field(default_factory=list)

    # File-specific
    file_path: Optional[str] = None
    file_operation: Optional[Literal["read", "write", "edit", "delete"]] = None

    # v0.3 forward-ported: Extended metadata
    model: Optional[str] = None
    tokens_used: Optional[int] = None
    tool_latency_ms: Optional[int] = None
    cache_hit: Optional[bool] = None
```

---

## Updated Success Criteria

### Must Have (0.2.2 Release)
- [ ] All sources appear in `mc mission-control`
- [ ] Status assignment is uniform (mtime-based)
- [ ] CLI shows session health widget
- [ ] Decision extraction from all sources (v0.3 Decision Ledger foundation)
- [ ] File touch tracking (v0.3 Conflict Radar foundation)
- [ ] 379+ tests passing

### Should Have
- [ ] Thinking surrogates for Codex/Gemini
- [ ] Backfill flag for mission_control
- [ ] Basic handoff export (v0.3 Session Handoff foundation)
- [ ] Context API (`mc context --json`)
- [ ] Redaction helper CLI (`mc redact`)

### Nice to Have
- [ ] Legacy code removed
- [ ] Single discovery path
- [ ] Documentation updated

### Stretch (0.2.2)
- [ ] Teleport command (`mc teleport <src> <dst>`)
- [ ] Test harness hints (`mc test-hints`)

---

## Agent-Facing APIs (Agent Self-Help Tools)

These are tools agents can call to help themselves, not just observability for users.

### 0.2.2 Release (Fits Builder Architecture)

| Feature | Implementation | Why Now |
|---------|---------------|---------|
| **Thinking Surrogates** | Each builder's `extract_thinking()` generates synthetic thinking for Codex/Gemini | Already in plan, fixes CoT gap |
| **Context API** | `mc context --json <session_id>` returns decisions, files, hot files as structured data | Builds on existing summary; agents can inject into prompts |
| **Session Tagging** | `UnifiedEvent.source` + `UnifiedSession.source` ensure consistent badges | Already in data structures |
| **Redaction Helper** | `mc redact <text>` CLI command; `redact(text)` Python API | Already exists in safety.py, just expose it |
| **Basic Handoff Export** | `mc handoff <session_id>` outputs portable context bundle | Already planned as `export_handoff()` |

### 0.2.2 Stretch (Build on Foundation)

| Feature | Implementation | Dependency |
|---------|---------------|------------|
| **Teleport** | `mc teleport <source_session> <target_session>` - inject context from one session into another | Needs handoff export + injection hook |
| **Test Harness Hints** | `mc test-hints` returns detected test commands for current repo | Simple detection, low risk |

### Deferred to 0.3.0 (Needs More Infrastructure)

| Feature | Why Defer | 0.3 Dependency |
|---------|----------|----------------|
| **Intent/Plan Spine** | Needs per-session storage system, set/get/update hooks | Cross-session memory system |
| **Guardrail/Policy Adapter** | Needs policy config system (`is_allowed(cmd)`) | Policy Packs (0.3 2.3) |
| **Checkpoint/Diff Helper** | Needs git wrapper (`checkpoint`, `rollback`, `diff`) | State Checkpoints (0.3 1.2) |
| **File/Ownership Map** | Needs cross-session file tracking | Conflict Radar (0.3 2.2) |
| **Process/Resource Awareness** | Nice-to-have, not critical path | Can add anytime |

---

## Teleport: Cross-Session Context Transfer

**Name:** Teleport (or "context graft")

**Purpose:** Take everything an agent "knows" from Session X and inject it into Session Y, enabling:
- Switching models mid-task (Claude → Codex)
- Resuming work after session timeout
- Handing off between agents

**0.2.2 Stretch Implementation:**

```python
# CLI
mc teleport <source_session_id> [--to <target_session_id>] [--format markdown|json]

# If --to is omitted, outputs to stdout (for manual injection)
# If --to is provided, appends a ThinkingEvent to target session
```

**What gets teleported:**
```python
@dataclass
class TeleportBundle:
    """Portable context for cross-session transfer."""
    # Identity
    source_session: str
    source_model: str  # claude-sonnet, gpt-4, etc.
    timestamp: datetime

    # Context (redacted, no raw file contents)
    intent: str              # What was the goal?
    decisions: List[str]     # Key decisions made
    files_touched: List[str] # Files read/modified (names only)
    hot_files: List[str]     # Most recently touched
    pending_todos: List[str] # Incomplete tasks
    last_action: str         # What was agent doing when stopped?

    # Safety
    warnings: List[str]      # "Session ended mid-edit", etc.
```

**What does NOT get teleported:**
- Raw file contents (security risk)
- API keys, secrets (redacted)
- Full conversation history (too large)
- Tool outputs (use summaries instead)

**Injection format (markdown):**
```markdown
## Context Teleported from Session {source_session}

**Original Task:** {intent}
**Model:** {source_model}
**Duration:** {duration}

### Decisions Made
- {decision_1}
- {decision_2}

### Files Touched
- {file_1} (modified)
- {file_2} (read)

### Pending Work
- [ ] {todo_1}
- [ ] {todo_2}

### Last Action
{last_action}

⚠️ {warning if any}
```

---

## Product Positioning

Based on this analysis, there may be **two products** emerging:

### Motus Command (mc) - Observability
- Watch agents work
- See decisions, tool calls, files touched
- Health monitoring
- Multi-source support (Claude, Codex, Gemini, SDK)

### Teleport / Aware - Agent Self-Help (Future)
- Tools agents call to help themselves
- Context injection, policy checks, test hints
- Cross-session continuity
- Intent/plan persistence

**For 0.2.2:** Keep them together. The agent-facing APIs are just CLI commands/SDK methods.

**For 0.3+:** Consider whether Teleport becomes a separate package or stays integrated
