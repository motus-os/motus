"""Tests for orchestrator cache."""

from datetime import datetime
from pathlib import Path

from motus.orchestrator.cache import (
    MAX_CACHED_EVENT_LISTS,
    MAX_CACHED_SESSIONS,
    SessionCache,
)
from motus.protocols import SessionStatus, Source, UnifiedSession


class TestSessionCache:
    """Test SessionCache class."""

    def test_cache_init(self):
        """Test cache initialization."""
        cache = SessionCache()
        assert cache._session_cache == {}
        assert cache._event_cache == {}
        assert cache._event_access_times == {}

    def test_get_session_miss(self):
        """Test get_session when session not in cache."""
        cache = SessionCache()
        result = cache.get_session("nonexistent")
        assert result is None

    def test_set_and_get_session(self):
        """Test setting and getting session."""
        cache = SessionCache()
        session = UnifiedSession(
            session_id="test-123",
            source=Source.CLAUDE,
            file_path=Path("/tmp/test.jsonl"),
            project_path="/project",
            status=SessionStatus.ACTIVE,
            status_reason="active",
            created_at=datetime.now(),
            last_modified=datetime.now(),
        )

        cache.set_session("test-123", session)
        result = cache.get_session("test-123")

        assert result is not None
        assert result.session_id == "test-123"

    def test_prune_session_cache_over_threshold(self):
        """Test pruning session cache when over threshold."""
        cache = SessionCache()

        # Add more sessions than threshold (120% of MAX)
        threshold = int(MAX_CACHED_SESSIONS * 1.2) + 5
        base_time = datetime.now()

        for i in range(threshold):
            session = UnifiedSession(
                session_id=f"session-{i}",
                source=Source.CLAUDE,
                file_path=Path(f"/tmp/session-{i}.jsonl"),
                project_path="/project",
                status=SessionStatus.IDLE,
                status_reason="idle",
                created_at=base_time,
                last_modified=base_time,
            )
            cache.set_session(session.session_id, session)

        # Should be over threshold
        assert len(cache._session_cache) > int(MAX_CACHED_SESSIONS * 1.2)

        # Prune should reduce to MAX
        cache.prune_caches()
        assert len(cache._session_cache) <= MAX_CACHED_SESSIONS

    def test_prune_event_cache_lru(self):
        """Test pruning event cache using LRU policy."""
        cache = SessionCache()

        # Fill event cache beyond limit
        for i in range(MAX_CACHED_EVENT_LISTS + 5):
            session_id = f"session-{i}"
            events = [{"event_id": f"e{i}"}]
            cache.set_events(session_id, events)

        # Should trigger pruning
        cache.prune_caches()
        assert len(cache._event_cache) <= MAX_CACHED_EVENT_LISTS

    def test_get_events_miss(self):
        """Test get_events when not in cache."""
        cache = SessionCache()
        result = cache.get_events("nonexistent")
        assert result is None

    def test_set_and_get_events(self):
        """Test setting and getting events."""
        cache = SessionCache()
        events = [{"event_id": "e1"}, {"event_id": "e2"}]

        cache.set_events("session-123", events)
        result = cache.get_events("session-123")

        assert result is not None
        assert len(result) == 2
        assert result[0]["event_id"] == "e1"

    def test_get_events_updates_access_time(self):
        """Test that getting events updates access time."""
        cache = SessionCache()
        events = [{"event_id": "e1"}]

        cache.set_events("session-123", events)
        initial_time = cache._event_access_times.get("session-123")

        # Small delay to ensure time difference
        import time

        time.sleep(0.01)

        cache.get_events("session-123")
        updated_time = cache._event_access_times.get("session-123")

        assert updated_time > initial_time

    def test_clear_all_caches(self):
        """Test clearing all caches."""
        cache = SessionCache()

        # Add some data
        session = UnifiedSession(
            session_id="test",
            source=Source.CLAUDE,
            file_path=Path("/tmp/test.jsonl"),
            project_path="/project",
            status=SessionStatus.IDLE,
            status_reason="idle",
            created_at=datetime.now(),
            last_modified=datetime.now(),
        )
        cache.set_session("test", session)
        cache.set_events("test", [{"event_id": "e1"}])

        # Clear
        cache.clear_all()

        assert len(cache._session_cache) == 0
        assert len(cache._event_cache) == 0
        assert len(cache._event_access_times) == 0

    def test_prune_parsed_event_cache(self):
        """Test pruning parsed event cache."""
        cache = SessionCache()

        # Fill parsed event cache beyond limit
        for i in range(MAX_CACHED_EVENT_LISTS + 3):
            session_id = f"session-{i}"
            events = []  # Empty list is fine for this test
            cache.set_parsed_events(session_id, events)

        # Should trigger pruning
        cache.prune_caches()
        assert len(cache._parsed_event_cache) <= MAX_CACHED_EVENT_LISTS

    def test_get_parsed_events_miss(self):
        """Test get_parsed_events when not in cache."""
        cache = SessionCache()
        result = cache.get_parsed_events("nonexistent")
        assert result is None

    def test_prune_with_no_access_times_fallback(self):
        """Test pruning fallback when access times are empty."""
        cache = SessionCache()

        # Add events but clear access times to test fallback
        for i in range(MAX_CACHED_EVENT_LISTS + 2):
            cache._event_cache[f"session-{i}"] = [{"event_id": f"e{i}"}]

        # Clear access times to trigger fallback path
        cache._event_access_times = {}

        # Should use fallback pruning (oldest key)
        cache.prune_caches()
        assert len(cache._event_cache) <= MAX_CACHED_EVENT_LISTS
