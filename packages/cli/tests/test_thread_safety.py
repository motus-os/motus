"""Thread safety tests for SQLite connections.

Verifies that database connections are configured with check_same_thread=False,
which prevents sqlite3.ProgrammingError when accessed from different threads.

Note: Full concurrent transaction safety requires additional locking (future work).
For v0.1.0, these components are CLI-only (single-threaded context).
"""

import sqlite3
import threading

import pytest


class TestSQLiteThreadSafety:
    """Test SQLite connections are configured for cross-thread access."""

    def test_database_manager_check_same_thread(self, tmp_path):
        """Verify DatabaseManager uses check_same_thread=False.

        This is the core test: can we access the same connection from another thread
        without getting sqlite3.ProgrammingError?
        """
        from motus.core.database_connection import DatabaseManager

        db_path = tmp_path / "test.db"
        manager = DatabaseManager(db_path)

        # Get connection in main thread
        conn = manager.get_connection()
        conn.execute("CREATE TABLE test (id INTEGER)")
        conn.execute("INSERT INTO test VALUES (1)")

        # Access from another thread should not raise ProgrammingError
        errors = []

        def access_from_thread():
            try:
                result = conn.execute("SELECT * FROM test").fetchall()
                assert len(result) == 1
            except sqlite3.ProgrammingError as e:
                errors.append(e)

        thread = threading.Thread(target=access_from_thread)
        thread.start()
        thread.join()

        assert not errors, f"Thread access failed: {errors}"
        manager.close()

    def test_lease_store_check_same_thread(self, tmp_path):
        """Verify LeaseStore uses check_same_thread=False."""
        from motus.coordination.api.lease_store import LeaseStore
        from motus.coordination.schemas import ClaimedResource as Resource

        store = LeaseStore(tmp_path / "leases.db")

        # Create lease in main thread
        lease = store.create_lease(
            owner_agent_id="test-agent",
            mode="write",
            resources=[Resource(type="file", path="/test.txt")],
            ttl_s=300,
            snapshot_id="snap-1",
            policy_version="v1",
            lens_digest="abc123",
        )

        # Read-only access from another thread should not raise ProgrammingError
        errors = []
        result_holder = []

        def read_from_thread():
            try:
                fetched = store.get_lease(lease.lease_id)
                result_holder.append(fetched)
            except sqlite3.ProgrammingError as e:
                errors.append(e)

        thread = threading.Thread(target=read_from_thread)
        thread.start()
        thread.join()

        assert not errors, f"Thread access failed with ProgrammingError: {errors}"
        assert result_holder[0] is not None
        store.close()

    def test_context_cache_check_same_thread(self, tmp_path):
        """Verify ContextCache uses check_same_thread=False."""
        from motus.context_cache.store import ContextCache

        cache = ContextCache(db_path=tmp_path / "cache.db")

        # Store in main thread
        cache.put_resource_spec(
            resource_type="file",
            resource_path="/test.txt",
            spec={"content": "hello"},
        )

        # Read-only access from another thread should not raise ProgrammingError
        errors = []

        def read_from_thread():
            try:
                # Just verify we can query without ProgrammingError
                cursor = cache._conn.execute(
                    "SELECT payload FROM resource_specs WHERE id = ?",
                    ("file:/test.txt",)
                )
                cursor.fetchone()
            except sqlite3.ProgrammingError as e:
                errors.append(e)

        thread = threading.Thread(target=read_from_thread)
        thread.start()
        thread.join()

        assert not errors, f"Thread access failed with ProgrammingError: {errors}"

    def test_session_store_check_same_thread(self, tmp_path):
        """Verify SessionStore uses check_same_thread=False.

        Note: SessionStore creates a new connection per operation via context manager,
        so this is inherently thread-safe (each thread gets its own connection).
        """
        from motus.session_store_core import SessionStore

        store = SessionStore(tmp_path / "sessions.db")

        # Create session in main thread
        session_id = store.create_session(tmp_path, "test-agent")

        # Read from another thread (gets its own connection via context manager)
        errors = []
        result_holder = []

        def read_from_thread():
            try:
                session = store.get_session(session_id)
                result_holder.append(session)
            except sqlite3.ProgrammingError as e:
                errors.append(e)

        thread = threading.Thread(target=read_from_thread)
        thread.start()
        thread.join()

        assert not errors, f"Thread access failed: {errors}"
        assert result_holder[0] is not None


# Note: Full concurrent transaction tests are deferred to v0.2.0
# Current stores use check_same_thread=False but don't have transaction locking.
# For v0.1.0, these are CLI-only (single-threaded) so this is acceptable.
