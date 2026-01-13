"""Migration validation tests.

These tests ensure migrations:
1. Execute without syntax errors (UP)
2. Rollback cleanly (DOWN)
3. Don't reference invalid foreign keys
4. Create expected tables and triggers

Added after FK mismatch and trailing comma bugs were found in production code.
"""

import sqlite3
import tempfile
from pathlib import Path

import pytest


MIGRATIONS_DIR = Path(__file__).parent.parent / "migrations"


def _get_migration_files():
    """Get all migration files sorted by version."""
    return sorted(MIGRATIONS_DIR.glob("*.sql"))


def _extract_up_sql(sql: str) -> str:
    """Extract UP section from migration SQL."""
    if "-- UP" in sql and "-- DOWN" in sql:
        return sql.split("-- DOWN")[0].split("-- UP")[1]
    return sql


def _extract_down_sql(sql: str) -> str | None:
    """Extract DOWN section from migration SQL."""
    if "-- DOWN" in sql:
        return sql.split("-- DOWN")[1]
    return None


@pytest.fixture
def fresh_db():
    """Create a fresh in-memory database."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    yield conn

    conn.close()
    Path(db_path).unlink(missing_ok=True)


class TestMigrationExecution:
    """Test that all migrations execute without errors."""

    def test_all_migrations_up(self, fresh_db):
        """All migrations should execute UP without syntax errors."""
        conn = fresh_db

        for migration_file in _get_migration_files():
            sql = migration_file.read_text()
            up_sql = _extract_up_sql(sql)

            try:
                conn.executescript(up_sql)
            except sqlite3.OperationalError as e:
                pytest.fail(
                    f"Migration {migration_file.name} UP failed: {e}\n"
                    f"Common causes:\n"
                    f"  - Trailing comma before comment-only lines\n"
                    f"  - FK referencing non-unique column\n"
                    f"  - Missing table from earlier migration"
                )

    def test_migration_down_rollback(self, fresh_db):
        """Migrations with DOWN sections should rollback cleanly."""
        conn = fresh_db

        # First run all UP
        for migration_file in _get_migration_files():
            sql = migration_file.read_text()
            up_sql = _extract_up_sql(sql)
            conn.executescript(up_sql)

        # Then run DOWN in reverse order
        for migration_file in reversed(_get_migration_files()):
            sql = migration_file.read_text()
            down_sql = _extract_down_sql(sql)

            if down_sql:
                try:
                    conn.executescript(down_sql)
                except sqlite3.OperationalError as e:
                    pytest.fail(
                        f"Migration {migration_file.name} DOWN failed: {e}"
                    )


class TestForeignKeyIntegrity:
    """Test that foreign keys are valid."""

    def test_no_fk_violations_after_up(self, fresh_db):
        """No FK violations should exist after running all UP migrations."""
        conn = fresh_db

        for migration_file in _get_migration_files():
            sql = migration_file.read_text()
            up_sql = _extract_up_sql(sql)
            conn.executescript(up_sql)

        # Check for FK violations
        cursor = conn.execute("PRAGMA foreign_key_check")
        violations = cursor.fetchall()

        if violations:
            details = "\n".join(str(v) for v in violations[:5])
            pytest.fail(
                f"Foreign key violations detected:\n{details}\n"
                f"Total: {len(violations)} violations"
            )

    def test_no_invalid_fk_targets(self, fresh_db):
        """FK targets should be PRIMARY KEY or UNIQUE columns."""
        conn = fresh_db

        for migration_file in _get_migration_files():
            sql = migration_file.read_text()
            up_sql = _extract_up_sql(sql)
            conn.executescript(up_sql)

        # Get all FKs and verify their targets
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
        tables = [row[0] for row in cursor.fetchall()]

        for table in tables:
            cursor = conn.execute(f"PRAGMA foreign_key_list({table})")
            fks = cursor.fetchall()

            for fk in fks:
                ref_table = fk[2]
                ref_col = fk[4]

                # Verify target column is indexed
                cursor = conn.execute(f"PRAGMA index_list({ref_table})")
                indexes = cursor.fetchall()

                # Check if ref_col is the rowid or in any unique index
                is_valid = False

                # Check table_info for PRIMARY KEY
                cursor = conn.execute(f"PRAGMA table_info({ref_table})")
                for col_info in cursor.fetchall():
                    if col_info[1] == ref_col and col_info[5]:  # pk column
                        is_valid = True
                        break

                if not is_valid:
                    # Check unique indexes
                    for idx in indexes:
                        if idx[2]:  # unique index
                            cursor = conn.execute(
                                f"PRAGMA index_info({idx[1]})"
                            )
                            idx_cols = [c[2] for c in cursor.fetchall()]
                            if ref_col in idx_cols:
                                is_valid = True
                                break

                if not is_valid:
                    pytest.fail(
                        f"Table {table} has FK to {ref_table}.{ref_col} "
                        f"which is not PRIMARY KEY or UNIQUE"
                    )


class TestExpectedSchema:
    """Test that expected schema elements are created."""

    def test_program_management_tables_exist(self, fresh_db):
        """Program management tables should exist after migrations."""
        conn = fresh_db

        for migration_file in _get_migration_files():
            sql = migration_file.read_text()
            up_sql = _extract_up_sql(sql)
            conn.executescript(up_sql)

        expected_tables = [
            "programs",
            "products",
            "features",
            "change_requests",
            "roadmap_items",
            "work_steps",
            "work_artifacts",
            "gate_outcomes",
            "bugs",
            "releases",
            "standards",
            "standard_assignments",
            "compliance_results",
            "charter_docs",
            "entity_versions",
        ]

        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
        actual_tables = {row[0] for row in cursor.fetchall()}

        missing = set(expected_tables) - actual_tables
        if missing:
            pytest.fail(f"Missing tables: {missing}")

    def test_immutability_triggers_exist(self, fresh_db):
        """Immutability triggers should protect audit tables."""
        conn = fresh_db

        for migration_file in _get_migration_files():
            sql = migration_file.read_text()
            up_sql = _extract_up_sql(sql)
            conn.executescript(up_sql)

        expected_triggers = [
            "audit_log_immutable",
            "audit_log_no_delete",
            "entity_versions_immutable",
            "entity_versions_no_delete",
            "compliance_immutable",
            "compliance_no_delete",
            "work_artifacts_no_update",
            "work_artifacts_no_delete",
            "gate_outcomes_no_update",
            "gate_outcomes_no_delete",
        ]

        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='trigger'"
        )
        actual_triggers = {row[0] for row in cursor.fetchall()}

        missing = set(expected_triggers) - actual_triggers
        if missing:
            pytest.fail(f"Missing immutability triggers: {missing}")


class TestSyntaxPatterns:
    """Test for common SQL syntax issues."""

    def test_no_trailing_commas_before_close_paren(self):
        """Detect trailing commas before closing parenthesis."""
        import re

        # Pattern: comma followed by optional whitespace/comments, then )
        # This catches: "column TEXT,\n    -- comment\n);"
        pattern = re.compile(r",\s*(?:--[^\n]*\n\s*)*\)", re.MULTILINE)

        for migration_file in _get_migration_files():
            sql = migration_file.read_text()

            matches = pattern.findall(sql)
            if matches:
                # Find line numbers for context
                lines = sql.split("\n")
                for i, line in enumerate(lines, 1):
                    if re.search(r",\s*$", line):
                        # Check if next non-comment line is )
                        for j in range(i, min(i + 5, len(lines))):
                            next_line = lines[j].strip()
                            if next_line.startswith("--"):
                                continue
                            if next_line.startswith(")"):
                                pytest.fail(
                                    f"{migration_file.name}:{i}: "
                                    f"Trailing comma before closing paren\n"
                                    f"  Line {i}: {line}\n"
                                    f"  Line {j+1}: {lines[j]}"
                                )
                            break
