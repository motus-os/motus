"""
Mock session data for deterministic snapshot tests.

This module provides mock SessionOrchestrator and session data that enables
snapshot tests to run without depending on live session files from
~/.claude/, ~/.codex/, ~/.gemini/.

Usage:
    from tests.fixtures.mock_sessions import MockOrchestrator, MOCK_SESSIONS
"""

from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

# Import protocols - handle both installed and dev paths
try:
    from motus.protocols import (
        EventType,
        SessionStatus,
        Source,
        UnifiedEvent,
        UnifiedSession,
    )
    from motus.schema.events import (
        AgentSource,
        ParsedEvent,
        RiskLevel,
    )
    from motus.schema.events import (
        EventType as SchemaEventType,
    )
except ImportError:
    try:
        from src.motus.protocols import (
            EventType,
            SessionStatus,
            Source,
            UnifiedEvent,
            UnifiedSession,
        )
        from src.motus.schema.events import (
            AgentSource,
            ParsedEvent,
            RiskLevel,
        )
        from src.motus.schema.events import (
            EventType as SchemaEventType,
        )
    except ImportError:
        EventType = None
        SessionStatus = None
        Source = None
        UnifiedEvent = None
        UnifiedSession = None
        ParsedEvent = None
        SchemaEventType = None
        AgentSource = None
        RiskLevel = None

# Fallback definitions if imports failed
if EventType is None:
    from enum import Enum

    class EventType(Enum):
        THINKING = "thinking"
        TOOL = "tool"
        FILE_READ = "file_read"
        FILE_MODIFIED = "file_modified"
        RESPONSE = "response"
        DECISION = "decision"
        AGENT_SPAWN = "spawn"

    # Bind back into module so downstream code sees a concrete enum
    import sys as _sys

    _sys.modules[__name__].EventType = EventType

if SessionStatus is None:
    from enum import Enum

    class SessionStatus(Enum):
        ACTIVE = "active"
        OPEN = "open"
        CRASHED = "crashed"
        IDLE = "idle"
        ORPHANED = "orphaned"

    import sys as _sys

    _sys.modules[__name__].SessionStatus = SessionStatus

if Source is None:
    from enum import Enum

    class Source(Enum):
        CLAUDE = "claude"
        CODEX = "codex"
        GEMINI = "gemini"
        SDK = "sdk"

    import sys as _sys

    _sys.modules[__name__].Source = Source


# ============================================================================
# Mock Session Data
# ============================================================================

# Use a fixed timestamp for deterministic snapshot tests
# This ensures snapshots don't change between runs
FIXED_TIMESTAMP = datetime(2025, 1, 15, 12, 0, 0)
NOW = FIXED_TIMESTAMP

MOCK_SESSIONS: List[UnifiedSession] = [
    UnifiedSession(
        session_id="claude-active-001",
        source=Source.CLAUDE,
        file_path=Path("/mock/.claude/projects/test-project/session.jsonl"),
        project_path="/Users/test/projects/web-app",
        created_at=NOW - timedelta(hours=2),
        last_modified=NOW - timedelta(minutes=2),
        status=SessionStatus.ACTIVE,
        status_reason="Recent tool call",
        event_count=45,
    ),
    UnifiedSession(
        session_id="codex-open-002",
        source=Source.CODEX,
        file_path=Path("/mock/.codex/sessions/codex-session.jsonl"),
        project_path="/Users/test/projects/api-server",
        created_at=NOW - timedelta(hours=3),
        last_modified=NOW - timedelta(minutes=15),
        status=SessionStatus.OPEN,
        status_reason="Process running, idle",
        event_count=23,
    ),
    UnifiedSession(
        session_id="claude-crashed-003",
        source=Source.CLAUDE,
        file_path=Path("/mock/.claude/projects/legacy/session.jsonl"),
        project_path="/Users/test/projects/legacy-app",
        created_at=NOW - timedelta(hours=4),
        last_modified=NOW - timedelta(hours=1),
        status=SessionStatus.CRASHED,
        status_reason="Unexpected termination",
        event_count=12,
    ),
    UnifiedSession(
        session_id="gemini-idle-004",
        source=Source.GEMINI,
        file_path=Path("/mock/.gemini/tmp/session.json"),
        project_path="/Users/test/projects/ml-pipeline",
        created_at=NOW - timedelta(hours=5),
        last_modified=NOW - timedelta(hours=2),
        status=SessionStatus.IDLE,
        status_reason="No process detected",
        event_count=8,
    ),
    UnifiedSession(
        session_id="claude-orphaned-005",
        source=Source.CLAUDE,
        file_path=Path("/mock/.claude/projects/old/session.jsonl"),
        project_path="/Users/test/projects/archived",
        created_at=NOW - timedelta(days=2),
        last_modified=NOW - timedelta(days=1),
        status=SessionStatus.ORPHANED,
        status_reason="Stale session",
        event_count=67,
    ),
]


# ============================================================================
# Mock Event Data
# ============================================================================


def _create_mock_events(session_id: str, count: int) -> List[UnifiedEvent]:
    """Generate deterministic mock events for a session."""
    events = []
    base_time = NOW - timedelta(hours=1)

    # Event templates matching actual EventType enum values from protocols.py
    event_templates = [
        (EventType.THINKING, "Analyzing the codebase structure...", None),
        (EventType.TOOL, "Tool: Read /test/src/main.py", "Read"),
        (EventType.FILE_READ, "Read: /test/src/main.py", None),
        (EventType.THINKING, "I need to modify the authentication module...", None),
        (EventType.TOOL, "Tool: Edit /test/src/auth.py", "Edit"),
        (EventType.FILE_MODIFIED, "Modified: /test/src/auth.py", None),
        (EventType.TOOL, "Tool: Bash - running tests", "Bash"),
        (EventType.RESPONSE, "I've updated the authentication module.", None),
        (EventType.DECISION, "Use async/await pattern for better performance", None),
    ]

    for i in range(min(count, 50)):
        template = event_templates[i % len(event_templates)]
        event_type, content, tool_name = template

        event = UnifiedEvent(
            event_id=f"{session_id}-event-{i:04d}",
            session_id=session_id,
            event_type=event_type,
            timestamp=base_time + timedelta(minutes=i),
            content=content,
            tool_name=tool_name,
            tool_input={"path": f"/test/file_{i}.py"} if tool_name else None,
            raw_data={},
        )
        events.append(event)

    return events


MOCK_EVENTS: Dict[str, List[UnifiedEvent]] = {
    session.session_id: _create_mock_events(session.session_id, session.event_count)
    for session in MOCK_SESSIONS
}


# ============================================================================
# Mock Orchestrator
# ============================================================================


class MockOrchestrator:
    """
    Mock SessionOrchestrator for deterministic testing.

    Provides the same interface as SessionOrchestrator but returns
    predefined mock data instead of discovering live sessions.
    """

    def __init__(
        self,
        sessions: Optional[List[UnifiedSession]] = None,
        events: Optional[Dict[str, List[UnifiedEvent]]] = None,
    ):
        """
        Initialize with custom or default mock data.

        Args:
            sessions: List of mock sessions. Defaults to MOCK_SESSIONS.
            events: Dict mapping session_id to events. Defaults to MOCK_EVENTS.
        """
        self._sessions = sessions or MOCK_SESSIONS
        self._events = events or MOCK_EVENTS
        self._session_cache = {s.session_id: s for s in self._sessions}
        # Track spawn depth per session for chain-of-thought visuals
        self._spawn_depth: Dict[str, int] = {}
        # Track pointer per session for paging-like behavior
        self._event_index: Dict[str, int] = {}

    def discover_all(
        self,
        max_age_hours: int = 24,
        sources: Optional[List[Source]] = None,
    ) -> List[UnifiedSession]:
        """Return mock sessions, optionally filtered by source."""
        if sources is None:
            return self._sessions

        return [s for s in self._sessions if s.source in sources]

    def get_session(self, session_id: str) -> Optional[UnifiedSession]:
        """Get a specific mock session by ID."""
        return self._session_cache.get(session_id)

    def get_events(
        self,
        session_id: str,
        since_index: int = 0,
        limit: Optional[int] = None,
    ) -> List[UnifiedEvent]:
        """Get mock events for a session."""
        all_events = self._events.get(session_id, [])
        start = since_index
        end = start + limit if limit else len(all_events)
        events = all_events[start:end]

        # Annotate with simple depth for spawn chains (cycle every 3)
        for ev in events:
            depth = 0
            if ev.event_type == EventType.AGENT_SPAWN:
                depth = self._spawn_depth.get(session_id, 0)
                self._spawn_depth[session_id] = depth + 1
            elif ev.event_type in (EventType.TOOL, EventType.THINKING):
                depth = self._spawn_depth.get(session_id, 0)
            ev.agent_depth = depth  # type: ignore[attr-defined]
        return events

    def get_events_validated(
        self,
        session: UnifiedSession,
        refresh: bool = False,
    ) -> List[ParsedEvent]:
        """Get mock events as validated ParsedEvent objects.

        This method is called by TUI to get ParsedEvent-compatible data.
        Converts UnifiedEvent to ParsedEvent for schema compatibility.
        """
        if ParsedEvent is None or SchemaEventType is None:
            return []  # Schema not available

        session_id = session.session_id
        unified_events = self.get_events(session_id)

        # Map protocol Source to schema AgentSource
        source_map = {
            Source.CLAUDE: AgentSource.CLAUDE,
            Source.CODEX: AgentSource.CODEX,
            Source.GEMINI: AgentSource.GEMINI,
        }
        agent_source = source_map.get(session.source, AgentSource.CLAUDE)

        # Map protocol EventType to schema EventType
        event_type_map = {
            EventType.THINKING: SchemaEventType.THINKING,
            EventType.TOOL: SchemaEventType.TOOL_USE,
            EventType.AGENT_SPAWN: SchemaEventType.AGENT_SPAWN,
            EventType.ERROR: SchemaEventType.ERROR,
            EventType.FILE_READ: SchemaEventType.TOOL_USE,
            EventType.FILE_MODIFIED: SchemaEventType.TOOL_USE,
        }

        parsed_events = []
        for ev in unified_events:
            try:
                schema_event_type = event_type_map.get(ev.event_type, SchemaEventType.THINKING)

                # Determine risk level
                risk = RiskLevel.SAFE
                if ev.tool_name in ("Edit", "Write"):
                    risk = RiskLevel.MEDIUM
                elif ev.tool_name == "Bash":
                    risk = RiskLevel.HIGH

                # Create longer content for thinking events to test expand/collapse
                content = ev.content or ""
                if schema_event_type == SchemaEventType.THINKING and len(content) < 250:
                    # Expand thinking events with additional reasoning
                    content = (
                        content
                        + "\n\nLet me break this down step by step:\n1. First, I need to understand the current architecture\n2. Then, identify potential improvements\n3. Finally, implement the changes carefully\n\nThis approach will ensure we maintain backward compatibility while adding the new features."
                    )

                parsed = ParsedEvent(
                    event_id=str(ev.event_id),
                    session_id=str(ev.session_id),
                    event_type=schema_event_type,
                    source=agent_source,
                    timestamp=ev.timestamp,
                    model=getattr(ev, "model", None),
                    risk_level=risk,
                    content=content,
                    tool_name=ev.tool_name,
                    tool_input=ev.tool_input,
                    tool_output=ev.tool_output,
                    spawn_type=getattr(ev, "agent_type", None),
                    spawn_prompt=getattr(ev, "agent_prompt", None),
                    agent_description=getattr(ev, "agent_description", None),
                )
                parsed_events.append(parsed)
            except Exception:
                # Skip events that fail validation
                continue

        return parsed_events

    def get_events_tail_validated(
        self,
        session: UnifiedSession,
        n_lines: int = 200,
    ) -> List[ParsedEvent]:
        """Get mock events as validated ParsedEvent objects (tail only).

        This method is called by TUI to get ParsedEvent-compatible data.
        Converts UnifiedEvent to ParsedEvent for schema compatibility.
        """
        if ParsedEvent is None or SchemaEventType is None:
            return []  # Schema not available

        session_id = session.session_id
        unified_events = self.get_events(session_id, limit=n_lines)

        # Map protocol Source to schema AgentSource
        source_map = {
            Source.CLAUDE: AgentSource.CLAUDE,
            Source.CODEX: AgentSource.CODEX,
            Source.GEMINI: AgentSource.GEMINI,
        }
        agent_source = source_map.get(session.source, AgentSource.CLAUDE)

        # Map protocol EventType to schema EventType
        event_type_map = {
            EventType.THINKING: SchemaEventType.THINKING,
            EventType.TOOL: SchemaEventType.TOOL_USE,
            EventType.AGENT_SPAWN: SchemaEventType.AGENT_SPAWN,
            EventType.ERROR: SchemaEventType.ERROR,
            EventType.FILE_READ: SchemaEventType.TOOL_USE,
            EventType.FILE_MODIFIED: SchemaEventType.TOOL_USE,
        }

        parsed_events = []
        for ev in unified_events:
            try:
                schema_event_type = event_type_map.get(ev.event_type, SchemaEventType.THINKING)

                # Determine risk level
                risk = RiskLevel.SAFE
                if ev.tool_name in ("Edit", "Write"):
                    risk = RiskLevel.MEDIUM
                elif ev.tool_name == "Bash":
                    risk = RiskLevel.HIGH

                # Create longer content for thinking events to test expand/collapse
                content = ev.content or ""
                if schema_event_type == SchemaEventType.THINKING and len(content) < 250:
                    # Expand thinking events with additional reasoning
                    content = (
                        content
                        + "\n\nLet me break this down step by step:\n1. First, I need to understand the current architecture\n2. Then, identify potential improvements\n3. Finally, implement the changes carefully\n\nThis approach will ensure we maintain backward compatibility while adding the new features."
                    )

                parsed = ParsedEvent(
                    event_id=str(ev.event_id),
                    session_id=str(ev.session_id),
                    event_type=schema_event_type,
                    source=agent_source,
                    timestamp=ev.timestamp,
                    model=getattr(ev, "model", None),
                    risk_level=risk,
                    content=content,
                    tool_name=ev.tool_name,
                    tool_input=ev.tool_input,
                    tool_output=ev.tool_output,
                    spawn_type=getattr(ev, "agent_type", None),
                    spawn_prompt=getattr(ev, "agent_prompt", None),
                    agent_description=getattr(ev, "agent_description", None),
                )
                parsed_events.append(parsed)
            except Exception:
                # Skip events that fail validation
                continue

        return parsed_events

    def get_context(self, session_id: str) -> dict:
        """Get mock context for a session."""
        session = self.get_session(session_id)
        if not session:
            return {}

        events = self.get_events(session_id)
        tool_counts = {}
        files_modified = []

        for event in events:
            if event.event_type == EventType.TOOL and event.tool_name:
                tool_counts[event.tool_name] = tool_counts.get(event.tool_name, 0) + 1
                if event.tool_name in ("Edit", "Write") and event.tool_input:
                    path = event.tool_input.get("path", "")
                    if path and path not in files_modified:
                        files_modified.append(path)

        return {
            "session_id": session_id,
            "source": session.source.value if hasattr(session.source, "value") else session.source,
            "project": str(session.project_path),
            "tool_count": tool_counts,
            "files_modified": files_modified,
            "decisions": ["Use async/await pattern", "Add error handling"],
            "friction_count": 1,
        }

    def is_process_degraded(self) -> bool:
        """Mock process detection health."""
        return False


# ============================================================================
# Pytest Fixtures
# ============================================================================


def get_mock_orchestrator() -> MockOrchestrator:
    """Factory function for creating MockOrchestrator instances."""
    return MockOrchestrator()


# For use with dependency injection
def mock_get_orchestrator() -> MockOrchestrator:
    """Drop-in replacement for get_orchestrator() in tests."""
    return MockOrchestrator()
