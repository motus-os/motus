from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from motus.core.migrations_schema import parse_migration_file


@pytest.fixture
def policy_db(tmp_path: Path) -> sqlite3.Connection:
    db_path = tmp_path / "policy_triggers.db"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(
        """
        CREATE TABLE roadmap_items (
            id TEXT PRIMARY KEY,
            phase_key TEXT NOT NULL,
            status_key TEXT NOT NULL DEFAULT 'pending',
            deleted_at TEXT DEFAULT NULL
        );
        """
    )

    # Apply all policy migrations in order
    for mig_file in [
        "008_claims_policy.sql",
        "009_fix_deploy_gate.sql",
        "010_fix_phase_limit_status.sql",
    ]:
        migration_path = Path(__file__).parent.parent / "migrations" / mig_file
        if migration_path.exists():
            migration = parse_migration_file(migration_path)
            conn.executescript(migration.up_sql)
    yield conn
    conn.close()


class TestDeployGate:
    def test_deploy_blocked_with_failed_claims(self, policy_db: sqlite3.Connection) -> None:
        policy_db.execute(
            """
            INSERT INTO claims (id, claim_text, page, claim_type, test_function, test_status)
            VALUES ('C-100', 'Claim text ok', 'index', 'quantitative', 'test_func', 'fail')
            """
        )

        with pytest.raises(sqlite3.IntegrityError, match="POLICY-001"):
            policy_db.execute(
                """
                INSERT INTO deployment_events (target, version, status)
                VALUES ('website', 'v0.1.0', 'pending')
                """
            )

    def test_deploy_blocked_with_pending_quantitative(self, policy_db: sqlite3.Connection) -> None:
        """HIGH priority fix: pending quantitative claims must block deploy."""
        policy_db.execute(
            """
            INSERT INTO claims (id, claim_text, page, claim_type, test_function, test_status)
            VALUES ('C-103', 'Claim text ok', 'index', 'quantitative', 'test_func', 'pending')
            """
        )

        with pytest.raises(sqlite3.IntegrityError, match="POLICY-002"):
            policy_db.execute(
                """
                INSERT INTO deployment_events (target, version, status)
                VALUES ('website', 'v0.1.0', 'pending')
                """
            )

    def test_deploy_allowed_with_pending_qualitative(self, policy_db: sqlite3.Connection) -> None:
        """Qualitative claims don't need verification - pending is OK."""
        policy_db.execute(
            """
            INSERT INTO claims (id, claim_text, page, claim_type, test_status)
            VALUES ('C-104', 'Claim text ok', 'index', 'qualitative', 'pending')
            """
        )

        # Should NOT raise - qualitative pending is acceptable
        policy_db.execute(
            """
            INSERT INTO deployment_events (target, version, status)
            VALUES ('website', 'v0.1.0', 'pending')
            """
        )
        row = policy_db.execute(
            "SELECT COUNT(*) as count FROM deployment_events"
        ).fetchone()
        assert row["count"] == 1

    def test_deploy_allowed_when_all_pass(self, policy_db: sqlite3.Connection) -> None:
        policy_db.execute(
            """
            INSERT INTO claims (id, claim_text, page, claim_type, test_function, test_status)
            VALUES ('C-101', 'Claim text ok', 'index', 'quantitative', 'test_func', 'pass')
            """
        )

        policy_db.execute(
            """
            INSERT INTO deployment_events (target, version, status)
            VALUES ('website', 'v0.1.0', 'pending')
            """
        )
        row = policy_db.execute(
            "SELECT COUNT(*) as count FROM deployment_events"
        ).fetchone()
        assert row["count"] == 1

    def test_deploy_gate_ignores_non_website(self, policy_db: sqlite3.Connection) -> None:
        policy_db.execute(
            """
            INSERT INTO claims (id, claim_text, page, claim_type, test_function, test_status)
            VALUES ('C-102', 'Claim text ok', 'index', 'quantitative', 'test_func', 'fail')
            """
        )

        policy_db.execute(
            """
            INSERT INTO deployment_events (target, version, status)
            VALUES ('docs', 'v0.1.0', 'pending')
            """
        )
        row = policy_db.execute(
            "SELECT COUNT(*) as count FROM deployment_events"
        ).fetchone()
        assert row["count"] == 1


class TestRoadmapPolicyTriggers:
    def test_completed_items_immutable(self, policy_db: sqlite3.Connection) -> None:
        policy_db.execute(
            """
            INSERT INTO roadmap_items (id, phase_key, status_key)
            VALUES ('RI-100', 'phase_a', 'completed')
            """
        )

        with pytest.raises(sqlite3.IntegrityError, match="Completed items cannot be modified"):
            policy_db.execute(
                """
                UPDATE roadmap_items
                SET status_key = 'pending'
                WHERE id = 'RI-100'
                """
            )

    def test_phase_limit_blocks_at_50(self, policy_db: sqlite3.Connection) -> None:
        items = [(f"RI-{i:03d}", "phase_a", "pending") for i in range(50)]
        policy_db.executemany(
            """
            INSERT INTO roadmap_items (id, phase_key, status_key)
            VALUES (?, ?, ?)
            """,
            items,
        )

        with pytest.raises(sqlite3.IntegrityError, match="Maximum 50 active items"):
            policy_db.execute(
                """
                INSERT INTO roadmap_items (id, phase_key, status_key)
                VALUES ('RI-050', 'phase_a', 'pending')
                """
            )

    def test_phase_limit_allows_under_50(self, policy_db: sqlite3.Connection) -> None:
        items = [(f"RI-{i:03d}", "phase_a", "pending") for i in range(49)]
        policy_db.executemany(
            """
            INSERT INTO roadmap_items (id, phase_key, status_key)
            VALUES (?, ?, ?)
            """,
            items,
        )

        policy_db.execute(
            """
            INSERT INTO roadmap_items (id, phase_key, status_key)
            VALUES ('RI-049', 'phase_a', 'pending')
            """
        )
        row = policy_db.execute(
            "SELECT COUNT(*) as count FROM roadmap_items WHERE phase_key = 'phase_a'"
        ).fetchone()
        assert row["count"] == 50

    def test_phase_limit_excludes_deferred(self, policy_db: sqlite3.Connection) -> None:
        """Deferred items don't count toward the 50 limit."""
        # Add 50 deferred items
        deferred = [(f"RI-D-{i:03d}", "phase_a", "deferred") for i in range(50)]
        policy_db.executemany(
            """
            INSERT INTO roadmap_items (id, phase_key, status_key)
            VALUES (?, ?, ?)
            """,
            deferred,
        )

        # Should succeed - deferred items don't count toward limit
        policy_db.execute(
            """
            INSERT INTO roadmap_items (id, phase_key, status_key)
            VALUES ('RI-NEW-001', 'phase_a', 'pending')
            """
        )
        row = policy_db.execute(
            "SELECT COUNT(*) as count FROM roadmap_items WHERE phase_key = 'phase_a'"
        ).fetchone()
        assert row["count"] == 51

    def test_phase_limit_excludes_completed(self, policy_db: sqlite3.Connection) -> None:
        """Completed items don't count toward the 50 limit."""
        # Add 50 completed items
        completed = [(f"RI-C-{i:03d}", "phase_a", "completed") for i in range(50)]
        policy_db.executemany(
            """
            INSERT INTO roadmap_items (id, phase_key, status_key)
            VALUES (?, ?, ?)
            """,
            completed,
        )

        # Should succeed - completed items don't count toward limit
        policy_db.execute(
            """
            INSERT INTO roadmap_items (id, phase_key, status_key)
            VALUES ('RI-NEW-002', 'phase_a', 'pending')
            """
        )
        row = policy_db.execute(
            "SELECT COUNT(*) as count FROM roadmap_items WHERE phase_key = 'phase_a'"
        ).fetchone()
        assert row["count"] == 51
