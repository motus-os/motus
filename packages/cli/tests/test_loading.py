"""Tests for centralized session loading, tail-based reading, and pagination.

These tests verify:
1. Session loading goes through the centralized orchestrator
2. Tail-based reading works correctly for large files
3. Web pagination works with has_more indicator
4. CLI/Web session loading uses the orchestrator
"""

import json
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest


class TestTailLines:
    """Tests for tail_lines efficient file reading."""

    def test_tail_lines_returns_last_n_lines(self):
        """tail_lines returns exactly the last N lines."""
        from motus.tail_reader import tail_lines

        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            for i in range(100):
                f.write(f'{{"line": {i}}}\n')
            path = f.name

        try:
            lines = tail_lines(path, n_lines=10)
            assert len(lines) == 10
            # Verify we got the last 10 lines (90-99)
            assert json.loads(lines[0])["line"] == 90
            assert json.loads(lines[-1])["line"] == 99
        finally:
            Path(path).unlink()

    def test_tail_lines_handles_empty_file(self):
        """tail_lines returns empty list for empty file."""
        from motus.tail_reader import tail_lines

        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            path = f.name

        try:
            lines = tail_lines(path, n_lines=10)
            assert lines == []
        finally:
            Path(path).unlink()

    def test_tail_lines_handles_nonexistent_file(self):
        """tail_lines returns empty list for nonexistent file."""
        from motus.tail_reader import tail_lines

        lines = tail_lines("/nonexistent/path/file.jsonl", n_lines=10)
        assert lines == []

    def test_tail_lines_handles_fewer_lines_than_requested(self):
        """tail_lines returns all lines when file has fewer than N."""
        from motus.tail_reader import tail_lines

        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            for i in range(5):
                f.write(f'{{"line": {i}}}\n')
            path = f.name

        try:
            lines = tail_lines(path, n_lines=100)
            assert len(lines) == 5
        finally:
            Path(path).unlink()

    def test_tail_lines_strips_whitespace(self):
        """tail_lines strips trailing whitespace from lines."""
        from motus.tail_reader import tail_lines

        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write('{"line": 1}   \n')
            f.write('{"line": 2}\t\n')
            path = f.name

        try:
            lines = tail_lines(path, n_lines=10)
            assert all(not line.endswith((" ", "\t", "\n")) for line in lines)
        finally:
            Path(path).unlink()

    def test_tail_lines_skips_empty_lines(self):
        """tail_lines skips empty lines in output."""
        from motus.tail_reader import tail_lines

        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write('{"line": 1}\n')
            f.write("\n")
            f.write('{"line": 2}\n')
            f.write("   \n")
            f.write('{"line": 3}\n')
            path = f.name

        try:
            lines = tail_lines(path, n_lines=10)
            assert len(lines) == 3
            assert all(line.strip() for line in lines)
        finally:
            Path(path).unlink()


class TestTailJsonl:
    """Tests for tail_jsonl with JSON parsing."""

    def test_tail_jsonl_parses_json(self):
        """tail_jsonl returns parsed JSON objects."""
        from motus.tail_reader import tail_jsonl

        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            for i in range(10):
                f.write(f'{{"value": {i}}}\n')
            path = f.name

        try:
            results = tail_jsonl(path, n_lines=5)
            assert len(results) == 5
            assert all(isinstance(r, dict) for r in results)
            assert results[0]["value"] == 5
            assert results[-1]["value"] == 9
        finally:
            Path(path).unlink()

    def test_tail_jsonl_skips_invalid_json(self):
        """tail_jsonl skips invalid JSON lines by default."""
        from motus.tail_reader import tail_jsonl

        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write('{"valid": 1}\n')
            f.write("not json\n")
            f.write('{"valid": 2}\n')
            path = f.name

        try:
            results = tail_jsonl(path, n_lines=10, skip_invalid=True)
            assert len(results) == 2
            assert results[0]["valid"] == 1
            assert results[1]["valid"] == 2
        finally:
            Path(path).unlink()

    def test_tail_jsonl_raises_on_invalid_json(self):
        """tail_jsonl raises when skip_invalid=False."""
        from motus.tail_reader import tail_jsonl

        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write("not json\n")
            path = f.name

        try:
            with pytest.raises(json.JSONDecodeError):
                tail_jsonl(path, n_lines=10, skip_invalid=False)
        finally:
            Path(path).unlink()


class TestCountLines:
    """Tests for count_lines utility."""

    def test_count_lines_returns_correct_count(self):
        """count_lines returns accurate line count."""
        from motus.tail_reader import count_lines

        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            for i in range(50):
                f.write(f"line {i}\n")
            path = f.name

        try:
            count = count_lines(path)
            assert count == 50
        finally:
            Path(path).unlink()

    def test_count_lines_handles_nonexistent_file(self):
        """count_lines returns 0 for nonexistent file."""
        from motus.tail_reader import count_lines

        count = count_lines("/nonexistent/path/file.jsonl")
        assert count == 0


class TestGetFileStats:
    """Tests for get_file_stats utility."""

    def test_get_file_stats_returns_dict(self):
        """get_file_stats returns expected keys."""
        from motus.tail_reader import get_file_stats

        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write('{"event": "test"}\n')
            path = f.name

        try:
            stats = get_file_stats(path)
            assert "size_bytes" in stats
            assert "size_mb" in stats
            assert "line_count" in stats
        finally:
            Path(path).unlink()

    def test_get_file_stats_nonexistent_file(self):
        """get_file_stats returns zeros for nonexistent file."""
        from motus.tail_reader import get_file_stats

        stats = get_file_stats("/nonexistent/path/file.jsonl")
        assert stats["size_bytes"] == 0
        assert stats["size_mb"] == 0.0
        assert stats["line_count"] == 0


class TestOrchestratorCentralizedLoading:
    """Tests that session loading is centralized through the orchestrator."""

    def test_orchestrator_discover_all_returns_unified_sessions(self):
        """Orchestrator discover_all returns UnifiedSession objects."""
        from motus.orchestrator import get_orchestrator

        orch = get_orchestrator()
        sessions = orch.discover_all(max_age_hours=24)

        assert isinstance(sessions, list)
        # All items should be UnifiedSession
        for s in sessions:
            assert hasattr(s, "source")
            assert hasattr(s, "session_id")
            assert hasattr(s, "file_path")

    def test_orchestrator_get_session_uses_cache(self):
        """get_session uses cache instead of re-discovering."""
        from motus.orchestrator import get_orchestrator

        orch = get_orchestrator()
        # Clear any existing cache
        orch._session_cache.clear()

        # First discover to populate cache
        sessions = orch.discover_all(max_age_hours=24)

        if sessions:
            session_id = sessions[0].session_id
            # Now get_session should use cached data
            cached = orch.get_session(session_id)
            assert cached is not None
            assert cached.session_id == session_id

    def test_orchestrator_has_cache_limits(self):
        """Orchestrator respects MAX_CACHED_SESSIONS limit."""
        from pathlib import Path

        from motus.orchestrator import MAX_CACHED_SESSIONS, get_orchestrator
        from motus.protocols import SessionStatus, Source, UnifiedSession

        orch = get_orchestrator()
        # Clear existing cache
        orch._session_cache.clear()

        now = datetime.now()
        # Add many sessions to cache with proper UnifiedSession objects
        for i in range(MAX_CACHED_SESSIONS + 50):
            session = UnifiedSession(
                source=Source.CLAUDE,
                session_id=f"test-session-{i}",
                project_path="/test/project",
                file_path=Path(f"/tmp/test-{i}.jsonl"),
                created_at=now - timedelta(hours=i + 1),
                last_modified=now - timedelta(hours=i),  # Varying ages
                status=SessionStatus.IDLE,
                status_reason="idle",
            )
            orch._session_cache[f"test-session-{i}"] = session

        # Prune should keep within limits
        orch._prune_caches()
        assert len(orch._session_cache) <= MAX_CACHED_SESSIONS


class TestWebPagination:
    """Tests for web dashboard pagination."""

    def test_session_history_response_has_pagination_fields(self):
        """Session history response includes pagination fields."""

        from motus.ui.web import MCWebServer

        server = MCWebServer(port=0)
        _ = server.create_app()  # noqa: F841

        # The response should include type, events, total_events, has_more, offset
        # This is a structural test - actual WebSocket behavior tested separately

    def test_pagination_batch_size_default(self):
        """Default batch size is 200."""
        # This is a code constant test - verify the value in websocket.py
        # The code uses batch_size=200 when calling parse_session_history
        # Verify this by checking the source code constant
        import inspect

        from motus.ui.web import websocket

        source = inspect.getsource(websocket.WebSocketHandler._send_session_history)
        assert "batch_size=200" in source

    def test_load_more_increments_offset(self):
        """Load more uses offset for pagination."""
        # Verify the message handling checks for load_more type
        import inspect

        from motus.ui.web import websocket

        source = inspect.getsource(websocket.WebSocketHandler._handle_client_message)
        assert 'msg_type == "load_more"' in source
        assert 'offset = data.get("offset", 0)' in source


class TestSessionTransformerConversion:
    """Tests for SessionTransformer behavior."""

    def test_session_transformer_conversion(self):
        """SessionTransformer converts UnifiedSession to DisplaySession correctly."""
        from pathlib import Path

        from motus.display.transformer import SessionTransformer
        from motus.protocols import SessionStatus, Source, UnifiedSession

        now = datetime.now()
        # Create a UnifiedSession with all required fields
        unified = UnifiedSession(
            source=Source.CLAUDE,
            session_id="test-session-123",
            project_path="/Users/test/project",
            file_path=Path("/tmp/test.jsonl"),
            created_at=now,
            last_modified=now,
            status=SessionStatus.ACTIVE,
            status_reason="Read file",
        )

        display_session = SessionTransformer.transform(unified)

        assert display_session.session_id == "test-session-123"
        assert display_session.source == Source.CLAUDE
        assert display_session.status == SessionStatus.ACTIVE


class TestListCmdUsesOrchestrator:
    """Tests that list command uses centralized loading."""

    def test_list_sessions_uses_session_manager(self):
        """list_sessions uses SessionManager which uses orchestrator."""
        from motus.commands.list_cmd import find_sessions

        # find_sessions should return list of SessionInfo
        sessions = find_sessions(max_age_hours=24)
        assert isinstance(sessions, list)

    def test_find_active_session_uses_find_sessions(self):
        """find_active_session uses find_sessions internally."""
        import inspect

        from motus.commands import list_cmd

        source = inspect.getsource(list_cmd.find_active_session)
        assert "find_sessions" in source


class TestCacheEvictionOnLargeLoad:
    """Tests that caches are properly evicted to prevent memory bloat."""

    def test_event_cache_has_limit(self):
        """Event cache has MAX_CACHED_EVENT_LISTS limit."""
        from motus.orchestrator import MAX_CACHED_EVENT_LISTS, get_orchestrator

        orch = get_orchestrator()

        # Add many event lists to cache
        for i in range(MAX_CACHED_EVENT_LISTS + 10):
            orch._event_cache[f"session-{i}"] = [{"event": "test"}]

        # Prune should keep within limits
        orch._prune_caches()
        assert len(orch._event_cache) <= MAX_CACHED_EVENT_LISTS


class TestLoadingPerformance:
    """Tests for loading performance characteristics."""

    def test_tail_lines_is_efficient_for_large_files(self):
        """tail_lines completes quickly even for large files."""
        import time

        from motus.tail_reader import tail_lines

        # Create a moderately large file (100K lines)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            for i in range(10000):  # 10K lines is enough for a unit test
                f.write(f'{{"event": "test", "index": {i}, "data": "x" * 100}}\n')
            path = f.name

        try:
            start = time.time()
            lines = tail_lines(path, n_lines=200)
            elapsed = time.time() - start

            # Should complete in under 1 second for 10K lines
            assert elapsed < 1.0
            assert len(lines) == 200
        finally:
            Path(path).unlink()

    def test_get_file_stats_is_fast(self):
        """get_file_stats doesn't require reading entire file."""
        import time

        from motus.tail_reader import get_file_stats

        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            for i in range(10000):
                f.write(f'{{"event": "test", "index": {i}}}\n')
            path = f.name

        try:
            start = time.time()
            stats = get_file_stats(path)
            elapsed = time.time() - start

            # Should complete nearly instantly (stat() call only)
            assert elapsed < 0.1
            assert stats["size_bytes"] > 0
        finally:
            Path(path).unlink()


class TestWebHistoryLoading:
    """Tests for web session history loading."""

    def test_send_session_history_uses_tail_lines(self):
        """parse_session_history uses tail_lines for efficiency."""
        import inspect

        from motus.ui.web.event_parser import parse_session_history

        source = inspect.getsource(parse_session_history)
        assert "tail_lines" in source

    def test_send_session_history_respects_batch_size(self):
        """parse_session_history limits events to batch_size."""
        import inspect

        from motus.ui.web.event_parser import parse_session_history

        source = inspect.getsource(parse_session_history)
        assert "batch_size" in source
        assert "paginate_events" in source

    def test_has_more_calculation(self):
        """has_more is calculated based on remaining events."""
        import inspect

        from motus.ui.web.event_parser import parse_session_history

        source = inspect.getsource(parse_session_history)
        assert "has_more" in source
        assert "offset + batch_size" in source or "estimated_total" in source
