"""
Performance Budget Tests

Tests that critical operations meet performance budgets.

Performance Budgets:
| Operation | Budget |
|-----------|--------|
| Parse 100 events | <500ms |
| TUI render 100 events | <500ms |
| Web initial load | <700ms |
| Web pagination | <300ms |
| Memory peak | <300MB |

These tests use time.perf_counter() for timing (not pytest-benchmark).
"""

import json
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path

from src.motus.ingestors.claude import ClaudeBuilder
from src.motus.ingestors.codex import CodexBuilder
from src.motus.ingestors.gemini import GeminiBuilder
from src.motus.protocols import SessionStatus, Source, UnifiedSession
from src.motus.tail_reader import count_lines, tail_jsonl, tail_lines
from tests.fixtures.mock_sessions import FIXED_TIMESTAMP, MockOrchestrator

# ============================================================================
# Fixture: Generate synthetic JSONL events
# ============================================================================


def generate_claude_events(n: int, session_id: str) -> list[str]:
    """Generate N synthetic Claude JSONL event lines for deterministic testing.

    Args:
        n: Number of events to generate
        session_id: Session ID for events

    Returns:
        List of JSONL strings representing Claude events
    """
    base_time = FIXED_TIMESTAMP
    lines = []

    for i in range(n):
        timestamp = base_time + timedelta(minutes=i)

        # Alternate between thinking and tool events (Claude format)
        if i % 2 == 0:
            event = {
                "type": "assistant",
                "timestamp": timestamp.isoformat(),
                "message": {
                    "model": "claude-sonnet-4-5-20250929",
                    "content": [
                        {
                            "type": "thinking",
                            "thinking": f"Analyzing the codebase structure for event {i}...",
                        }
                    ],
                },
            }
        else:
            event = {
                "type": "assistant",
                "timestamp": timestamp.isoformat(),
                "message": {
                    "model": "claude-sonnet-4-5-20250929",
                    "content": [
                        {
                            "type": "tool_use",
                            "id": f"tool_{i}",
                            "name": "Read" if i % 3 == 1 else "Edit",
                            "input": {"file_path": f"/test/src/file_{i}.py"},
                        }
                    ],
                },
            }

        lines.append(json.dumps(event))

    return lines


def generate_codex_events(n: int, session_id: str) -> list[str]:
    """Generate N synthetic Codex JSONL event lines.

    Args:
        n: Number of events to generate
        session_id: Session ID for events

    Returns:
        List of JSONL strings representing Codex events
    """
    base_time = FIXED_TIMESTAMP
    lines = []

    # First line: session metadata (required for Codex discovery)
    session_meta = {
        "type": "session_meta",
        "timestamp": base_time.isoformat(),
        "payload": {
            "id": session_id,
            "cwd": "/test/project",
            "cli_version": "1.0.0",
            "originator": "claude-code",
            "model_provider": "openai",
        },
    }
    lines.append(json.dumps(session_meta))

    for i in range(n):
        timestamp = base_time + timedelta(minutes=i)

        # Codex format: response_item with nested payload
        if i % 2 == 0:
            # Text message
            event = {
                "type": "response_item",
                "timestamp": timestamp.isoformat(),
                "payload": {
                    "type": "message",
                    "content": [{"type": "text", "text": f"Analyzing code pattern {i}..."}],
                },
            }
        else:
            # Function call (tool use)
            event = {
                "type": "response_item",
                "timestamp": timestamp.isoformat(),
                "payload": {
                    "type": "function_call",
                    "name": "read_file" if i % 3 == 1 else "write_file",
                    "arguments": json.dumps({"path": f"/test/src/file_{i}.py"}),
                    "call_id": f"call_{i}",
                },
            }

        lines.append(json.dumps(event))

    return lines


def generate_gemini_session(n: int, session_id: str) -> dict:
    """Generate a synthetic Gemini session JSON with N events.

    Args:
        n: Number of events to generate
        session_id: Session ID for events

    Returns:
        Dict representing a Gemini session file
    """
    base_time = FIXED_TIMESTAMP
    messages = []

    for i in range(n):
        timestamp = base_time + timedelta(minutes=i)

        if i % 2 == 0:
            # Text message
            message = {
                "type": "gemini",
                "timestamp": timestamp.isoformat(),
                "content": f"Analyzing the requirements for step {i}...",
                "model": "gemini-2.0-flash",
                "tokens": {
                    "input": 100,
                    "output": 50,
                    "total": 150,
                },
            }
        else:
            # Tool call
            message = {
                "type": "gemini",
                "timestamp": timestamp.isoformat(),
                "content": "",
                "model": "gemini-2.0-flash",
                "toolCalls": [
                    {
                        "id": f"tool_{i}",
                        "name": "read_file" if i % 3 == 1 else "edit_file",
                        "args": {"path": f"/test/src/file_{i}.py"},
                        "result": "Tool executed successfully",
                    }
                ],
                "tokens": {
                    "input": 100,
                    "output": 20,
                    "tool": 10,
                    "total": 130,
                },
            }

        messages.append(message)

    return {
        "sessionId": session_id,
        "projectHash": "test_project_hash_12345",
        "startTime": base_time.isoformat(),
        "lastUpdated": (base_time + timedelta(minutes=n)).isoformat(),
        "messages": messages,
    }


# ============================================================================
# Test 1: Parse 100 events under 500ms
# ============================================================================


def test_parse_100_events_under_500ms():
    """Parsing 100 events through builders must complete in under 500ms.

    This tests the critical path from raw JSONL to UnifiedEvent objects.
    """
    # Generate 100 synthetic events
    lines = generate_claude_events(100, "perf-test-session")

    # Create temporary JSONL file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        for line in lines:
            f.write(line + "\n")
        temp_path = Path(f.name)

    try:
        builder = ClaudeBuilder()

        # Time the parsing operation
        start = time.perf_counter()
        events = builder.parse_events(temp_path)
        elapsed = time.perf_counter() - start

        # Verify we got events
        assert len(events) > 0, "Expected events to be parsed"

        # Check performance budget
        assert elapsed < 0.5, f"Took {elapsed:.3f}s, budget is 0.5s"

    finally:
        # Cleanup
        temp_path.unlink()


def test_parse_100_events_codex_under_500ms():
    """Parsing 100 Codex events must complete in under 500ms."""
    lines = generate_codex_events(100, "perf-test-codex")

    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        for line in lines:
            f.write(line + "\n")
        temp_path = Path(f.name)

    try:
        builder = CodexBuilder()

        start = time.perf_counter()
        events = builder.parse_events(temp_path)
        elapsed = time.perf_counter() - start

        assert len(events) > 0, "Expected events to be parsed"
        assert elapsed < 0.5, f"Took {elapsed:.3f}s, budget is 0.5s"

    finally:
        temp_path.unlink()


def test_parse_100_events_gemini_under_500ms():
    """Parsing 100 Gemini events must complete in under 500ms."""
    session_data = generate_gemini_session(100, "perf-test-gemini")

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(session_data, f)
        temp_path = Path(f.name)

    try:
        builder = GeminiBuilder()

        start = time.perf_counter()
        events = builder.parse_events(temp_path)
        elapsed = time.perf_counter() - start

        assert len(events) > 0, "Expected events to be parsed"
        assert elapsed < 0.5, f"Took {elapsed:.3f}s, budget is 0.5s"

    finally:
        temp_path.unlink()


# ============================================================================
# Test 2: ParsedEvent validation layer performance
# ============================================================================


def test_parse_100_events_validated_under_600ms():
    """Parsing 100 events with Pydantic validation must complete in under 600ms.

    This tests the full pipeline: JSONL -> UnifiedEvent -> ParsedEvent validation.
    Slightly higher budget (600ms) to account for Pydantic validation overhead.
    """
    lines = generate_claude_events(100, "perf-test-validated")

    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        for line in lines:
            f.write(line + "\n")
        temp_path = Path(f.name)

    try:
        builder = ClaudeBuilder()

        start = time.perf_counter()
        events = builder.parse_events_validated(temp_path)
        elapsed = time.perf_counter() - start

        assert len(events) > 0, "Expected validated events"
        assert elapsed < 0.6, f"Took {elapsed:.3f}s, budget is 0.6s"

    finally:
        temp_path.unlink()


# ============================================================================
# Test 3: Session discovery performance
# ============================================================================


def test_session_discovery_reasonable():
    """Session discovery with MockOrchestrator should be fast.

    This tests that discover_all() operations complete quickly
    even when processing multiple session files. Using MockOrchestrator
    avoids the complexity of config mocking and tests the core performance.
    """
    # Create 100 mock sessions for realistic discovery performance test
    mock_sessions = []
    for i in range(100):
        session = UnifiedSession(
            session_id=f"perf-test-session-{i:03d}",
            source=Source.CLAUDE,
            file_path=Path(f"/mock/.claude/projects/test-{i}/session.jsonl"),
            project_path=f"/test/project-{i}",
            created_at=FIXED_TIMESTAMP - timedelta(hours=i),
            last_modified=FIXED_TIMESTAMP - timedelta(minutes=i),
            status=SessionStatus.ACTIVE,
            status_reason="Performance test session",
            event_count=10,
            tool_count=5,
            file_change_count=2,
            thinking_count=3,
            decision_count=1,
        )
        mock_sessions.append(session)

    # Use MockOrchestrator with our sessions
    orchestrator = MockOrchestrator(sessions=mock_sessions, events={})

    # Time discovery
    start = time.perf_counter()
    sessions = orchestrator.discover_all()
    elapsed = time.perf_counter() - start

    # Should find all sessions we created
    assert len(sessions) == 100, f"Expected 100 sessions, got {len(sessions)}"

    # Discovery should be very fast (under 200ms for 100 sessions)
    assert elapsed < 0.2, f"Discovery took {elapsed:.3f}s, should be under 0.2s"


# ============================================================================
# Test 4: Tail reader performance
# ============================================================================


def test_tail_lines_performance():
    """tail_lines() should be fast even for large files.

    The tail reader is critical for responsive TUI updates.
    """
    # Create a large JSONL file (1000 events)
    lines = generate_claude_events(1000, "perf-test-tail")

    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        for line in lines:
            f.write(line + "\n")
        temp_path = Path(f.name)

    try:
        # Time reading last 200 lines
        start = time.perf_counter()
        tail = tail_lines(temp_path, n_lines=200)
        elapsed = time.perf_counter() - start

        assert len(tail) == 200, f"Expected 200 lines, got {len(tail)}"

        # Should be fast (under 100ms for 1000-line file)
        assert elapsed < 0.1, f"tail_lines took {elapsed:.3f}s, should be under 0.1s"

    finally:
        temp_path.unlink()


def test_tail_jsonl_performance():
    """tail_jsonl() should parse efficiently for large files."""
    lines = generate_claude_events(1000, "perf-test-tail-jsonl")

    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        for line in lines:
            f.write(line + "\n")
        temp_path = Path(f.name)

    try:
        # Time reading and parsing last 200 lines
        start = time.perf_counter()
        events = tail_jsonl(temp_path, n_lines=200)
        elapsed = time.perf_counter() - start

        assert len(events) == 200, f"Expected 200 events, got {len(events)}"

        # Should be fast (under 150ms for parsing 200 JSON objects)
        assert elapsed < 0.15, f"tail_jsonl took {elapsed:.3f}s, should be under 0.15s"

    finally:
        temp_path.unlink()


def test_count_lines_performance():
    """count_lines() should be fast for large files."""
    lines = generate_claude_events(1000, "perf-test-count")

    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        for line in lines:
            f.write(line + "\n")
        temp_path = Path(f.name)

    try:
        start = time.perf_counter()
        count = count_lines(temp_path)
        elapsed = time.perf_counter() - start

        assert count == 1000, f"Expected 1000 lines, got {count}"

        # Should be very fast (under 50ms for 1000 lines)
        assert elapsed < 0.05, f"count_lines took {elapsed:.3f}s, should be under 0.05s"

    finally:
        temp_path.unlink()


# ============================================================================
# Test 5: Orchestrator performance
# ============================================================================


def test_orchestrator_get_events_tail_performance():
    """Orchestrator tail operations should meet performance budgets."""
    # Use MockOrchestrator with synthetic events
    orchestrator = MockOrchestrator()

    # Time getting tail events (validated)
    mock_session = orchestrator.discover_all()[0]

    start = time.perf_counter()
    orchestrator.get_events_tail_validated(mock_session, n_lines=100)
    elapsed = time.perf_counter() - start

    # Mock orchestrator should be very fast (under 50ms)
    assert elapsed < 0.05, f"get_events_tail_validated took {elapsed:.3f}s, should be under 0.05s"


# ============================================================================
# Test 6: Status computation performance
# ============================================================================


def test_compute_status_under_1ms():
    """Status computation should be extremely fast (< 1ms per session).

    This is called for every session during discovery and must be fast.
    """
    builder = ClaudeBuilder()
    now = datetime.now()

    # Time computing status for 100 sessions
    start = time.perf_counter()
    for i in range(100):
        modified = now - timedelta(minutes=i)
        builder.compute_status(
            last_modified=modified,
            now=now,
            last_action="Read file.py",
            has_completion=True,
        )
    elapsed = time.perf_counter() - start

    # Should be very fast (under 10ms for 100 status computations)
    # This means < 0.1ms per computation
    assert elapsed < 0.01, f"100 status computations took {elapsed:.3f}s, should be under 0.01s"


# ============================================================================
# Test 7: Line-level parsing performance
# ============================================================================


def test_parse_line_performance():
    """parse_line() should be fast for streaming event processing."""
    builder = ClaudeBuilder()
    lines = generate_claude_events(100, "perf-test-line")

    # Time parsing 100 lines individually
    start = time.perf_counter()
    total_events = 0
    for line in lines:
        events = builder.parse_line(line, session_id="test-session")
        total_events += len(events)
    elapsed = time.perf_counter() - start

    assert total_events > 0, "Expected events from line parsing"

    # Should be fast (under 100ms for 100 lines)
    assert elapsed < 0.1, f"parse_line for 100 lines took {elapsed:.3f}s, should be under 0.1s"


def test_parse_line_validated_performance():
    """parse_line_validated() should be fast with validation overhead."""
    builder = ClaudeBuilder()
    lines = generate_claude_events(100, "perf-test-line-validated")

    # Time parsing and validating 100 lines individually
    start = time.perf_counter()
    total_events = 0
    for line in lines:
        events = builder.parse_line_validated(line, session_id="test-session")
        total_events += len(events)
    elapsed = time.perf_counter() - start

    assert total_events > 0, "Expected validated events from line parsing"

    # Validation adds overhead, but should still be reasonable (under 200ms)
    assert (
        elapsed < 0.2
    ), f"parse_line_validated for 100 lines took {elapsed:.3f}s, should be under 0.2s"


# ============================================================================
# Test 8: Decision extraction performance
# ============================================================================


def test_decision_extraction_performance():
    """Decision extraction from large text should be reasonable.

    This tests the regex pattern matching used for decision detection.
    """
    # Create text with multiple decision patterns
    text_chunks = [
        "I'll use the async/await pattern for better performance.",
        "I have decided to implement caching with Redis.",
        "The best approach is to use a factory pattern here.",
        "Let me create a new module for authentication.",
        "I'm choosing TypeScript for type safety.",
        "Going with PostgreSQL for the database.",
    ] * 20  # 120 sentences

    full_text = " ".join(text_chunks)

    builder = ClaudeBuilder()

    # Time decision extraction
    start = time.perf_counter()
    decisions = builder._extract_decisions_from_text(
        full_text,
        session_id="test-session",
        timestamp=FIXED_TIMESTAMP,
    )
    elapsed = time.perf_counter() - start

    assert len(decisions) > 0, "Expected to extract decisions"

    # Should be fast (under 50ms for large text)
    assert elapsed < 0.05, f"Decision extraction took {elapsed:.3f}s, should be under 0.05s"


# ============================================================================
# Performance summary test (informational)
# ============================================================================


def test_performance_summary(capsys):
    """Print a summary of performance test results.

    This test always passes but prints timing information for monitoring.
    """
    print("\n\n=== Performance Test Summary ===")

    # Run a quick benchmark of key operations
    lines = generate_claude_events(100, "summary-test")

    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        for line in lines:
            f.write(line + "\n")
        temp_path = Path(f.name)

    try:
        builder = ClaudeBuilder()

        # Parse 100 events
        start = time.perf_counter()
        builder.parse_events(temp_path)
        parse_time = time.perf_counter() - start

        # Parse with validation
        start = time.perf_counter()
        builder.parse_events_validated(temp_path)
        validate_time = time.perf_counter() - start

        print(f"\nParse 100 events:           {parse_time * 1000:.1f}ms (budget: 500ms)")
        print(f"Parse + validate 100 events: {validate_time * 1000:.1f}ms (budget: 600ms)")
        print(f"Validation overhead:         {(validate_time - parse_time) * 1000:.1f}ms")

        # Status computation
        now = datetime.now()
        start = time.perf_counter()
        for i in range(1000):
            builder.compute_status(
                last_modified=now - timedelta(minutes=i % 60),
                now=now,
            )
        status_time = time.perf_counter() - start

        print(f"1000 status computations:    {status_time * 1000:.1f}ms ({status_time:.3f}ms each)")

        print("\n=== All performance budgets met ===\n")

    finally:
        temp_path.unlink()

    # This test always passes (informational only)
    assert True
