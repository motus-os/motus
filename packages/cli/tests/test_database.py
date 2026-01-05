"""Tests for core database functionality.

Tests:
- DatabaseManager with WAL mode
- MigrationRunner with version tracking
- Bootstrap on fresh install
- Schema version checking
- Error handling
"""

import json
import sqlite3
from pathlib import Path

import pytest

from motus.core import (
    DatabaseManager,
    MigrationError,
    SchemaError,
)
from motus.core.bootstrap import bootstrap_database, is_first_run
from motus.core.migrations import MigrationRunner
from motus.core.migrations_schema import parse_migration_file


class TestDatabaseManager:
    """Test DatabaseManager functionality."""

    def test_database_creation(self, tmp_path):
        """Test creating a fresh database."""
        db_path = tmp_path / "test.db"
        db = DatabaseManager(db_path)

        # Get connection (should create database)
        conn = db.get_connection()
        assert db_path.exists()
        assert conn is not None

        # Verify WAL mode enabled
        result = conn.execute("PRAGMA journal_mode").fetchone()
        assert result[0] == "wal"

        # Verify foreign keys enabled
        result = conn.execute("PRAGMA foreign_keys").fetchone()
        assert result[0] == 1

        db.checkpoint_and_close()

    def test_creates_parent_directory(self, tmp_path):
        """Test that DatabaseManager creates the parent directory."""
        db_path = tmp_path / "nested" / "db.sqlite3"
        assert not db_path.parent.exists()

        db = DatabaseManager(db_path)
        db.get_connection()

        assert db_path.exists()
        assert db_path.parent.exists()

        db.checkpoint_and_close()

    def test_connection_reuse(self, tmp_path):
        """Test that connections are reused."""
        db_path = tmp_path / "test.db"
        db = DatabaseManager(db_path)

        conn1 = db.get_connection()
        conn2 = db.get_connection()

        # Should be same connection object
        assert conn1 is conn2

        db.checkpoint_and_close()

    def test_context_manager(self, tmp_path):
        """Test using connection via context manager."""
        db_path = tmp_path / "test.db"
        db = DatabaseManager(db_path)

        with db.connection() as conn:
            # Should be able to execute queries
            conn.execute("CREATE TABLE test (id INTEGER PRIMARY KEY)")
            conn.execute("INSERT INTO test VALUES (1)")

        # Verify data persisted
        with db.connection() as conn:
            result = conn.execute("SELECT * FROM test").fetchone()
            assert result[0] == 1

        db.checkpoint_and_close()

    def test_file_permissions(self, tmp_path):
        """Test that database files have secure permissions (600)."""
        db_path = tmp_path / "test.db"
        db = DatabaseManager(db_path)
        db.get_connection()

        # Check file permissions
        import stat

        mode = db_path.stat().st_mode
        # Should be readable and writable by owner only
        assert mode & stat.S_IRUSR  # Owner read
        assert mode & stat.S_IWUSR  # Owner write
        assert not (mode & stat.S_IRGRP)  # Group no read
        assert not (mode & stat.S_IROTH)  # Others no read

        db.checkpoint_and_close()

    def test_wal_size_check(self, tmp_path):
        """Test WAL size monitoring."""
        db_path = tmp_path / "test.db"
        db = DatabaseManager(db_path)

        # Create database and make some writes
        with db.connection() as conn:
            conn.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, data TEXT)")
            for i in range(100):
                conn.execute("INSERT INTO test VALUES (?, ?)", (i, "x" * 1000))

        # Check WAL size
        status, size = db.check_wal_size()
        assert status in ("ok", "warning", "checkpoint_forced")
        assert size >= 0

        db.checkpoint_and_close()

    def test_record_metric_inserts_row(self, tmp_path):
        """record_metric creates metrics table and inserts a row."""
        db_path = tmp_path / "test.db"
        db = DatabaseManager(db_path)

        db.record_metric("list_sessions", 12.5, metadata={"source": "sqlite"})

        with db.connection() as conn:
            columns = {
                row[1]
                for row in conn.execute("PRAGMA table_info(metrics)").fetchall()
            }
            success_column = "is_success" if "is_success" in columns else "success"
            row = conn.execute(
                f"SELECT operation, elapsed_ms, {success_column}, metadata FROM metrics"
            ).fetchone()

        assert row is not None
        assert row["operation"] == "list_sessions"
        assert row[success_column] == 1
        metadata = json.loads(row["metadata"])
        assert metadata["source"] == "sqlite"


class TestMigrationRunner:
    """Test MigrationRunner functionality."""

    def test_discover_migrations(self, tmp_path):
        """Test discovering migration files."""
        migrations_dir = tmp_path / "migrations"
        migrations_dir.mkdir()

        # Create test migration files
        (migrations_dir / "001_first.sql").write_text(
            """
-- Migration: 001_first
-- Version: 1

-- UP
CREATE TABLE test1 (id INTEGER PRIMARY KEY);

-- DOWN
DROP TABLE IF EXISTS test1;
"""
        )

        (migrations_dir / "002_second.sql").write_text(
            """
-- Migration: 002_second
-- Version: 2

-- UP
CREATE TABLE test2 (id INTEGER PRIMARY KEY);

-- DOWN
DROP TABLE IF EXISTS test2;
"""
        )

        # Create database
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(db_path, isolation_level=None)

        # Run discovery
        runner = MigrationRunner(conn, migrations_dir)
        migrations = runner.discover_migrations()

        assert len(migrations) == 2
        assert migrations[0].version == 1
        assert migrations[0].name == "first"
        assert migrations[1].version == 2
        assert migrations[1].name == "second"

        conn.close()

    def test_apply_migrations(self, tmp_path):
        """Test applying migrations."""
        migrations_dir = tmp_path / "migrations"
        migrations_dir.mkdir()

        # Create migration
        (migrations_dir / "001_create_users.sql").write_text(
            """
-- Migration: 001_create_users
-- Version: 1

-- UP
CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL
);

-- DOWN
DROP TABLE IF EXISTS users;
"""
        )

        # Create database and apply migrations
        # NOTE: Use default isolation_level (not None) to avoid transaction conflicts
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(db_path)

        runner = MigrationRunner(conn, migrations_dir)
        count = runner.apply_migrations()

        assert count == 1

        # Verify table exists
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='users'"
        )
        assert cursor.fetchone() is not None

        # Verify schema_version table updated
        cursor = conn.execute("SELECT version FROM schema_version")
        versions = [row[0] for row in cursor.fetchall()]
        assert versions == [1]

        conn.close()

    def test_migration_idempotency(self, tmp_path):
        """Test that migrations can be run multiple times safely."""
        migrations_dir = tmp_path / "migrations"
        migrations_dir.mkdir()

        (migrations_dir / "001_test.sql").write_text(
            """
-- Migration: 001_test
-- Version: 1

-- UP
CREATE TABLE test (id INTEGER PRIMARY KEY);

-- DOWN
DROP TABLE IF EXISTS test;
"""
        )

        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(db_path)

        runner = MigrationRunner(conn, migrations_dir)

        # Run migrations twice
        count1 = runner.apply_migrations()
        count2 = runner.apply_migrations()

        assert count1 == 1
        assert count2 == 0  # No new migrations applied

        conn.close()

    def test_migration_checksum_verification(self, tmp_path):
        """Test that modified migrations are detected."""
        migrations_dir = tmp_path / "migrations"
        migrations_dir.mkdir()

        migration_file = migrations_dir / "001_test.sql"
        migration_file.write_text(
            """
-- Migration: 001_test
-- Version: 1

-- UP
CREATE TABLE test (id INTEGER PRIMARY KEY);

-- DOWN
DROP TABLE IF EXISTS test;
"""
        )

        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(db_path)

        runner = MigrationRunner(conn, migrations_dir)
        runner.apply_migrations()

        # Modify migration file (simulate tampering)
        migration_file.write_text(
            """
-- Migration: 001_test
-- Version: 1

-- UP
CREATE TABLE test (id INTEGER PRIMARY KEY, extra TEXT);

-- DOWN
DROP TABLE IF EXISTS test;
"""
        )

        # Should detect checksum mismatch
        runner2 = MigrationRunner(conn, migrations_dir)
        with pytest.raises(MigrationError, match="MIGRATE-002.*checksum"):
            runner2.apply_migrations()

        conn.close()

    def test_legacy_leases_upgrade(self, tmp_path):
        """Allow checksum mismatches for known migrations and upgrade legacy leases."""
        migrations_dir = Path(__file__).resolve().parents[1] / "migrations"
        db_path = tmp_path / "legacy.db"
        conn = sqlite3.connect(db_path, isolation_level=None)

        conn.execute(
            """
            CREATE TABLE schema_version (
                version INTEGER PRIMARY KEY,
                migration_name TEXT NOT NULL,
                applied_at TEXT NOT NULL DEFAULT (datetime('now')),
                checksum TEXT NOT NULL,
                execution_time_ms INTEGER
            )
            """
        )

        allowlist = {
            5: "8e25ba0db729df46",
            11: "916955d0d4a93548",
            16: "fb79675f0195b2a0",
        }
        for path in sorted(migrations_dir.glob("*.sql")):
            migration = parse_migration_file(path)
            if migration.version >= 19:
                continue
            checksum = allowlist.get(migration.version, migration.checksum)
            conn.execute(
                """
                INSERT INTO schema_version (version, migration_name, checksum, execution_time_ms)
                VALUES (?, ?, ?, ?)
                """,
                (migration.version, migration.name, checksum, 0),
            )

        conn.executescript(
            """
            CREATE TABLE leases (
                lease_id TEXT PRIMARY KEY,
                owner_agent_id TEXT NOT NULL,
                mode TEXT NOT NULL,
                resources TEXT NOT NULL,
                issued_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                heartbeat_deadline TEXT NOT NULL,
                snapshot_id TEXT NOT NULL,
                policy_version TEXT NOT NULL,
                lens_digest TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                outcome TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """
        )

        # Minimal roadmap tables needed for migration 020 cleanup
        conn.executescript(
            """
            CREATE TABLE roadmap_items (
                id TEXT PRIMARY KEY,
                created_by TEXT
            );
            CREATE TABLE roadmap_assignments (
                item_id TEXT
            );
            CREATE TABLE roadmap_dependencies (
                item_id TEXT,
                depends_on_id TEXT
            );
            """
        )

        runner = MigrationRunner(conn, migrations_dir)
        count = runner.apply_migrations()

        assert count == 2
        cols = {row[1] for row in conn.execute("PRAGMA table_info(leases)").fetchall()}
        assert "resource_type" in cols
        legacy = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'leases_legacy%'"
        ).fetchall()
        assert legacy

        conn.close()

    def test_migration_rollback(self, tmp_path):
        """Test rolling back a migration."""
        migrations_dir = tmp_path / "migrations"
        migrations_dir.mkdir()

        (migrations_dir / "001_test.sql").write_text(
            """
-- Migration: 001_test
-- Version: 1

-- UP
CREATE TABLE test (id INTEGER PRIMARY KEY);

-- DOWN
DROP TABLE IF EXISTS test;
"""
        )

        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(db_path)

        runner = MigrationRunner(conn, migrations_dir)
        runner.apply_migrations()

        # Verify table exists
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='test'"
        )
        assert cursor.fetchone() is not None

        # Rollback migration
        runner.rollback_migration(1)

        # Verify table removed
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='test'"
        )
        assert cursor.fetchone() is None

        # Verify schema_version updated
        cursor = conn.execute("SELECT version FROM schema_version")
        assert cursor.fetchone() is None

        conn.close()

    def test_get_current_version(self, tmp_path):
        """Test getting current schema version."""
        migrations_dir = tmp_path / "migrations"
        migrations_dir.mkdir()

        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(db_path)

        runner = MigrationRunner(conn, migrations_dir)

        # Fresh database should be version 0
        assert runner.get_current_version() == 0

        # Apply migration
        (migrations_dir / "001_test.sql").write_text(
            """
-- Migration: 001_test
-- Version: 1

-- UP
CREATE TABLE test (id INTEGER PRIMARY KEY);

-- DOWN
DROP TABLE IF EXISTS test;
"""
        )

        runner.apply_migrations()
        assert runner.get_current_version() == 1

        conn.close()


class TestBootstrap:
    """Test bootstrap functionality."""

    def test_is_first_run_detection(self, tmp_path, monkeypatch):
        """Test detecting first run (no database)."""
        # Mock get_database_path to use tmp_path
        monkeypatch.setattr(
            "motus.core.bootstrap.get_database_path",
            lambda: tmp_path / "motus.db",
        )

        # Should be first run (no DB exists)
        assert is_first_run() is True

        # Create database
        (tmp_path / "motus.db").touch()

        # Should not be first run
        assert is_first_run() is False

    def test_bootstrap_applies_migrations(self, tmp_path, monkeypatch):
        """Test that bootstrap applies migrations on first run."""
        # Create database directory (simulates normal filesystem where ~ exists)
        db_dir = tmp_path / "motus"
        db_dir.mkdir(mode=0o700)
        db_path = db_dir / "motus.db"

        # Mock configuration
        monkeypatch.setattr(
            "motus.core.bootstrap.get_database_path", lambda: db_path
        )
        monkeypatch.setattr(
            "motus.core.database.get_database_path", lambda: db_path
        )

        # Mock migrations directory
        migrations_dir = tmp_path / "migrations"
        migrations_dir.mkdir()

        # Create minimal migration
        (migrations_dir / "001_init.sql").write_text(
            """
-- Migration: 001_init
-- Version: 1

-- UP
CREATE TABLE test (id INTEGER PRIMARY KEY);

-- DOWN
DROP TABLE IF EXISTS test;
"""
        )
        (migrations_dir / "002_next.sql").write_text(
            """
-- Migration: 002_next
-- Version: 2

-- UP
CREATE TABLE test2 (id INTEGER PRIMARY KEY);

-- DOWN
DROP TABLE IF EXISTS test2;
"""
        )
        (migrations_dir / "003_third.sql").write_text(
            """
-- Migration: 003_third
-- Version: 3

-- UP
CREATE TABLE test3 (id INTEGER PRIMARY KEY);

-- DOWN
DROP TABLE IF EXISTS test3;
"""
        )
        (migrations_dir / "004_fourth.sql").write_text(
            """
-- Migration: 004_fourth
-- Version: 4

-- UP
CREATE TABLE test4 (id INTEGER PRIMARY KEY);

-- DOWN
DROP TABLE IF EXISTS test4;
"""
        )
        (migrations_dir / "005_fifth.sql").write_text(
            """
-- Migration: 005_fifth
-- Version: 5

-- UP
CREATE TABLE test5 (id INTEGER PRIMARY KEY);

-- DOWN
DROP TABLE IF EXISTS test5;
"""
        )
        (migrations_dir / "006_sixth.sql").write_text(
            """
-- Migration: 006_sixth
-- Version: 6

-- UP
CREATE TABLE test6 (id INTEGER PRIMARY KEY);

-- DOWN
DROP TABLE IF EXISTS test6;
"""
        )

        monkeypatch.setattr(
            "motus.core.bootstrap._get_migrations_dir",
            lambda: migrations_dir,
        )
        # Match test's 6 fake migrations
        monkeypatch.setattr(
            "motus.core.database_connection.EXPECTED_SCHEMA_VERSION", 6
        )

        # Run bootstrap
        bootstrap_database()

        # Verify database created
        assert db_path.exists()

        # Verify table was created by migration
        import sqlite3

        conn = sqlite3.connect(db_path)
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='test'"
        )
        assert cursor.fetchone() is not None
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='test2'"
        )
        assert cursor.fetchone() is not None
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='test3'"
        )
        assert cursor.fetchone() is not None
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='test4'"
        )
        assert cursor.fetchone() is not None
        conn.close()


class TestErrorHandling:
    """Test error handling and edge cases."""

    def test_disk_full_error_detection(self, tmp_path):
        """Test detecting disk full errors."""
        from motus.core.errors import is_disk_error

        # Simulate various disk errors
        disk_errors = [
            sqlite3.OperationalError("disk I/O error"),
            sqlite3.OperationalError("database or disk is full"),
            sqlite3.OperationalError("unable to open database file"),
        ]

        for error in disk_errors:
            assert is_disk_error(error) is True

        # Non-disk errors
        other_error = sqlite3.OperationalError("syntax error")
        assert is_disk_error(other_error) is False

    def test_schema_version_mismatch(self, tmp_path):
        """Test detecting schema version mismatch."""
        from motus.core.database import (
            EXPECTED_SCHEMA_VERSION,
            verify_schema_version,
        )

        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(db_path, isolation_level=None)

        # Create schema_version table with wrong version
        conn.execute(
            """
            CREATE TABLE schema_version (
                version INTEGER PRIMARY KEY,
                migration_name TEXT NOT NULL,
                applied_at TEXT NOT NULL DEFAULT (datetime('now')),
                checksum TEXT NOT NULL,
                execution_time_ms INTEGER
            )
        """
        )

        # Insert old version
        conn.execute(
            "INSERT INTO schema_version VALUES (?, ?, datetime('now'), 'abc', 100)",
            (EXPECTED_SCHEMA_VERSION - 1, "old_migration"),
        )

        # Should raise SchemaError for old version
        with pytest.raises(SchemaError, match="DB-SCHEMA-001.*older"):
            verify_schema_version(conn)

        # Test newer version
        conn.execute("DELETE FROM schema_version")
        conn.execute(
            "INSERT INTO schema_version VALUES (?, ?, datetime('now'), 'abc', 100)",
            (EXPECTED_SCHEMA_VERSION + 1, "future_migration"),
        )

        with pytest.raises(SchemaError, match="DB-SCHEMA-002.*newer"):
            verify_schema_version(conn)

        conn.close()


class TestDNACompliance:
    """Test compliance with DNA-DB-SQLITE rules."""

    def test_wal_mode_enabled(self, tmp_path):
        """Test RULE 1: WAL mode enabled on connection."""
        db_path = tmp_path / "test.db"
        db = DatabaseManager(db_path)
        conn = db.get_connection()

        result = conn.execute("PRAGMA journal_mode").fetchone()
        assert result[0] == "wal"

        db.checkpoint_and_close()

    def test_foreign_keys_enabled(self, tmp_path):
        """Test RULE 1: Foreign keys enforced."""
        db_path = tmp_path / "test.db"
        db = DatabaseManager(db_path)
        conn = db.get_connection()

        result = conn.execute("PRAGMA foreign_keys").fetchone()
        assert result[0] == 1

        # Test enforcement
        conn.execute("CREATE TABLE parent (id INTEGER PRIMARY KEY)")
        conn.execute(
            """
            CREATE TABLE child (
                id INTEGER PRIMARY KEY,
                parent_id INTEGER REFERENCES parent(id)
            )
        """
        )

        # Should fail - parent doesn't exist
        with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
            conn.execute("INSERT INTO child VALUES (1, 999)")

        db.checkpoint_and_close()

    def test_busy_timeout_set(self, tmp_path):
        """Test RULE 1: Busy timeout configured."""
        db_path = tmp_path / "test.db"
        db = DatabaseManager(db_path)
        conn = db.get_connection()

        result = conn.execute("PRAGMA busy_timeout").fetchone()
        assert result[0] == 30000  # 30 seconds

        db.checkpoint_and_close()

    def test_row_factory_enabled(self, tmp_path):
        """Test RULE 1: Row factory for dict-like access."""
        db_path = tmp_path / "test.db"
        db = DatabaseManager(db_path)
        conn = db.get_connection()

        conn.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, name TEXT)")
        conn.execute("INSERT INTO test VALUES (1, 'test')")

        row = conn.execute("SELECT * FROM test").fetchone()

        # Should support dict-like access
        assert row["id"] == 1
        assert row["name"] == "test"

        db.checkpoint_and_close()

    def test_crash_recovery_rolls_back_uncommitted_writes(self, tmp_path):
        """Test crash recovery behavior for uncommitted writes (DB-SQL-016)."""
        from motus.core.database import _configure_connection

        db_path = tmp_path / "crash.db"

        # Write inside an explicit transaction, then "crash" (close without COMMIT).
        conn = sqlite3.connect(str(db_path), isolation_level=None)
        _configure_connection(conn)
        conn.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, value TEXT)")
        conn.execute("BEGIN IMMEDIATE")
        conn.execute("INSERT INTO test (value) VALUES (?)", ("before_crash",))
        conn.close()  # No COMMIT => should be rolled back

        # Re-open and verify rollback + integrity.
        conn2 = sqlite3.connect(str(db_path), isolation_level=None)
        _configure_connection(conn2)
        count = conn2.execute(
            "SELECT COUNT(*) FROM test WHERE value = ?",
            ("before_crash",),
        ).fetchone()[0]
        assert count == 0

        integrity = conn2.execute("PRAGMA integrity_check").fetchone()[0]
        assert integrity == "ok"
        conn2.close()
