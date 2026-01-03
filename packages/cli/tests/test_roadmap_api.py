"""Tests for frictionless Roadmap API.

Tests validate:
- 6-call API surface (ready, claim, complete, status, release, my_work)
- Stripe "Pit of Success" pattern (actionable next steps)
- Dependency enforcement (can't claim blocked items)
- Agent assignment isolation
"""

import sqlite3
from pathlib import Path

import pytest

from motus.core.roadmap import RoadmapAPI, RoadmapResponse


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    """Create a temp database path."""
    return tmp_path / "test_roadmap.db"


@pytest.fixture
def setup_db(db_path: Path) -> sqlite3.Connection:
    """Set up test database with schema and test data."""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    # Create minimal schema
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS schema_version (
            version INTEGER PRIMARY KEY,
            applied_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        INSERT INTO schema_version (version) VALUES (8);

        CREATE TABLE IF NOT EXISTS roadmap_items (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            status_key TEXT NOT NULL DEFAULT 'pending',
            rank REAL DEFAULT 0.0,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            deleted_at TEXT DEFAULT NULL
        );

        CREATE TABLE IF NOT EXISTS roadmap_dependencies (
            item_id TEXT NOT NULL,
            depends_on_id TEXT NOT NULL,
            dependency_type TEXT NOT NULL DEFAULT 'blocks',
            PRIMARY KEY (item_id, depends_on_id)
        );

        CREATE TABLE IF NOT EXISTS roadmap_assignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id TEXT NOT NULL,
            agent_id TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'assigned',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            completed_at TEXT DEFAULT NULL
        );

        CREATE TABLE IF NOT EXISTS assignment_prerequisites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_assignment_id INTEGER NOT NULL,
            prerequisite_item_id TEXT NOT NULL,
            depth INTEGER NOT NULL DEFAULT 1
        );

        -- View: Ready items (no incomplete blocking deps)
        CREATE VIEW IF NOT EXISTS v_ready_items AS
        SELECT ri.id, ri.title, ri.status_key, ri.rank
        FROM roadmap_items ri
        WHERE ri.deleted_at IS NULL
          AND ri.status_key IN ('pending', 'in_progress')
          AND NOT EXISTS (
              SELECT 1 FROM roadmap_dependencies rd
              JOIN roadmap_items blocker ON blocker.id = rd.depends_on_id
              WHERE rd.item_id = ri.id
                AND rd.dependency_type = 'blocks'
                AND blocker.status_key != 'completed'
          );

        -- View: Prerequisite chain
        CREATE VIEW IF NOT EXISTS v_prerequisite_chain AS
        WITH RECURSIVE prereq_chain(root_item_id, prereq_id, prereq_title, prereq_status, depth) AS (
            SELECT rd.item_id, rd.depends_on_id, ri.title, ri.status_key, 1
            FROM roadmap_dependencies rd
            JOIN roadmap_items ri ON ri.id = rd.depends_on_id
            WHERE rd.dependency_type = 'blocks' AND ri.deleted_at IS NULL
            UNION ALL
            SELECT pc.root_item_id, rd.depends_on_id, ri.title, ri.status_key, pc.depth + 1
            FROM prereq_chain pc
            JOIN roadmap_dependencies rd ON rd.item_id = pc.prereq_id
            JOIN roadmap_items ri ON ri.id = rd.depends_on_id
            WHERE rd.dependency_type = 'blocks' AND ri.deleted_at IS NULL AND pc.depth < 50
        )
        SELECT DISTINCT root_item_id, prereq_id, prereq_title, prereq_status, depth,
            CASE WHEN prereq_status = 'completed' THEN 1 ELSE 0 END as is_complete
        FROM prereq_chain
        ORDER BY root_item_id, depth, prereq_id;

        -- Test data: Independent items
        INSERT INTO roadmap_items (id, title, status_key, rank)
        VALUES
            ('ITEM-001', 'First task', 'pending', 1.0),
            ('ITEM-002', 'Second task', 'pending', 2.0),
            ('ITEM-003', 'Third task', 'pending', 3.0);

        -- Test data: Blocked item
        INSERT INTO roadmap_items (id, title, status_key, rank)
        VALUES ('BLOCKED-001', 'Blocked task', 'pending', 4.0);

        INSERT INTO roadmap_dependencies (item_id, depends_on_id, dependency_type)
        VALUES ('BLOCKED-001', 'ITEM-001', 'blocks');

        -- Test data: Completed item
        INSERT INTO roadmap_items (id, title, status_key, rank)
        VALUES ('DONE-001', 'Done task', 'completed', 0.5);
        """
    )
    conn.commit()
    return conn


@pytest.fixture
def api(db_path: Path, setup_db: sqlite3.Connection, monkeypatch) -> RoadmapAPI:
    """Create API instance with test database."""
    # Patch get_db_manager to use our test database
    from motus.core import database_connection

    class TestDBManager:
        def __init__(self):
            self.db_path = db_path
            self._connection = setup_db

        def connection(self):
            from contextlib import contextmanager

            @contextmanager
            def ctx():
                yield self._connection

            return ctx()

        def transaction(self):
            from contextlib import contextmanager

            @contextmanager
            def ctx():
                self._connection.execute("BEGIN IMMEDIATE")
                try:
                    yield self._connection
                    self._connection.execute("COMMIT")
                except Exception:
                    self._connection.execute("ROLLBACK")
                    raise

            return ctx()

        def get_connection(self):
            return self._connection

    test_manager = TestDBManager()
    monkeypatch.setattr(database_connection, "_db_manager", test_manager)
    monkeypatch.setattr(
        database_connection, "get_db_manager", lambda: test_manager
    )

    return RoadmapAPI(agent_id="test-agent")


class TestReady:
    """Tests for ready() - what can I work on?"""

    def test_returns_unblocked_items(self, api: RoadmapAPI):
        """ready() returns items without blocking dependencies."""
        result = api.ready()
        assert result.success is True
        assert len(result.data) >= 3  # ITEM-001, 002, 003
        assert all(item.id != "BLOCKED-001" for item in result.data)

    def test_includes_actionable_next_step(self, api: RoadmapAPI):
        """ready() includes action and command (Stripe pattern)."""
        result = api.ready()
        assert result.action != ""
        assert result.command.startswith("mc roadmap")

    def test_ordered_by_rank(self, api: RoadmapAPI):
        """ready() returns items in rank order."""
        result = api.ready()
        ranks = [item.rank for item in result.data]
        assert ranks == sorted(ranks)


class TestClaim:
    """Tests for claim() - claim an item for work."""

    def test_claim_unblocked_item(self, api: RoadmapAPI):
        """Can claim an item with no blocking dependencies."""
        result = api.claim("ITEM-001")
        assert result.success is True
        assert result.data["item_id"] == "ITEM-001"
        assert "complete" in result.command.lower()

    def test_claim_blocked_item_fails(self, api: RoadmapAPI):
        """Cannot claim an item with incomplete blockers."""
        result = api.claim("BLOCKED-001")
        assert result.success is False
        assert "ROAD-002" in result.message
        assert len(result.blockers) > 0
        # Action should point to first blocker
        assert "ITEM-001" in result.command

    def test_claim_nonexistent_fails(self, api: RoadmapAPI):
        """Cannot claim item that doesn't exist."""
        result = api.claim("DOES-NOT-EXIST")
        assert result.success is False
        assert "ROAD-001" in result.message

    def test_claim_already_claimed_by_self(self, api: RoadmapAPI):
        """Re-claiming own item returns success."""
        api.claim("ITEM-001")
        result = api.claim("ITEM-001")
        assert result.success is True
        assert result.data["status"] == "already_claimed"

    def test_claim_already_claimed_by_other(
        self, api: RoadmapAPI, setup_db: sqlite3.Connection
    ):
        """Cannot claim item claimed by another agent."""
        # Pre-claim by another agent
        setup_db.execute(
            """
            INSERT INTO roadmap_assignments (item_id, agent_id, status)
            VALUES ('ITEM-002', 'other-agent', 'assigned')
            """
        )
        setup_db.commit()

        result = api.claim("ITEM-002")
        assert result.success is False
        assert "ROAD-003" in result.message
        assert "other-agent" in result.message


class TestComplete:
    """Tests for complete() - mark item done."""

    def test_complete_own_item(self, api: RoadmapAPI, monkeypatch):
        """Reviewer can complete an item assigned to self."""
        monkeypatch.setenv("MC_REVIEWER", "1")
        api.claim("ITEM-001")
        result = api.complete("ITEM-001")
        assert result.success is True

    def test_complete_requires_reviewer(self, api: RoadmapAPI):
        """Builder cannot complete items directly."""
        result = api.complete("ITEM-001")
        assert result.success is False
        assert "ROAD-010" in result.message

    def test_complete_unassigned_fails(self, api: RoadmapAPI, monkeypatch):
        """Reviewer cannot complete an unassigned item."""
        monkeypatch.setenv("MC_REVIEWER", "1")
        result = api.complete("ITEM-002")
        assert result.success is False
        assert "ROAD-006" in result.message
        assert "claim" in result.command.lower()

    def test_complete_others_item_allowed_for_reviewer(
        self, api: RoadmapAPI, setup_db: sqlite3.Connection, monkeypatch
    ):
        """Reviewer can complete item assigned to another agent."""
        monkeypatch.setenv("MC_REVIEWER", "1")
        setup_db.execute(
            """
            INSERT INTO roadmap_assignments (item_id, agent_id, status)
            VALUES ('ITEM-002', 'other-agent', 'assigned')
            """
        )
        setup_db.commit()

        result = api.complete("ITEM-002")
        assert result.success is True

    def test_complete_unblocks_dependents(self, api: RoadmapAPI, monkeypatch):
        """Reviewer completing blocker shows newly unblocked items."""
        monkeypatch.setenv("MC_REVIEWER", "1")
        api.claim("ITEM-001")
        result = api.complete("ITEM-001")
        assert result.success is True
        # BLOCKED-001 should now be unblocked
        if result.data.get("unblocked"):
            assert "BLOCKED-001" in result.data["unblocked"]


class TestStatus:
    """Tests for status() - check item status."""

    def test_status_completed_item(self, api: RoadmapAPI):
        """status() shows completed items correctly."""
        result = api.status("DONE-001")
        assert result.success is True
        assert result.data.status == "completed"
        assert "ready" in result.command.lower()

    def test_status_blocked_item(self, api: RoadmapAPI):
        """status() shows blockers for blocked items."""
        result = api.status("BLOCKED-001")
        assert result.success is True
        assert result.data.is_blocked is True
        assert len(result.blockers) > 0
        assert "ITEM-001" in result.command  # Points to first blocker

    def test_status_ready_item(self, api: RoadmapAPI):
        """status() for ready item suggests claiming."""
        result = api.status("ITEM-001")
        assert result.success is True
        assert result.data.is_blocked is False
        assert "claim" in result.command.lower()

    def test_status_nonexistent(self, api: RoadmapAPI):
        """status() for missing item returns error."""
        result = api.status("DOES-NOT-EXIST")
        assert result.success is False
        assert "ROAD-001" in result.message


class TestRelease:
    """Tests for release() - release claim without completing."""

    def test_release_own_claim(self, api: RoadmapAPI):
        """Can release own claim."""
        api.claim("ITEM-001")
        result = api.release("ITEM-001")
        assert result.success is True

    def test_release_unassigned_fails(self, api: RoadmapAPI):
        """Cannot release unassigned item."""
        result = api.release("ITEM-002")
        assert result.success is False
        assert "ROAD-006" in result.message

    def test_release_others_claim_fails(
        self, api: RoadmapAPI, setup_db: sqlite3.Connection
    ):
        """Cannot release another agent's claim."""
        setup_db.execute(
            """
            INSERT INTO roadmap_assignments (item_id, agent_id, status)
            VALUES ('ITEM-002', 'other-agent', 'assigned')
            """
        )
        setup_db.commit()

        result = api.release("ITEM-002")
        assert result.success is False


class TestReview:
    """Tests for review() - update item status."""

    def test_review_updates_status(self, api: RoadmapAPI, setup_db: sqlite3.Connection):
        """review() updates status to review."""
        result = api.review("ITEM-001")
        assert result.success is True
        assert result.data["new_status"] == "review"

        row = setup_db.execute(
            "SELECT status_key FROM roadmap_items WHERE id = ?",
            ("ITEM-001",),
        ).fetchone()
        assert row["status_key"] == "review"

    def test_review_invalid_status(self, api: RoadmapAPI):
        """review() rejects invalid status."""
        result = api.review("ITEM-001", status="invalid")
        assert result.success is False
        assert "Invalid status" in result.message

    def test_review_missing_item(self, api: RoadmapAPI):
        """review() fails for missing item."""
        result = api.review("NOPE-001")
        assert result.success is False
        assert "ROAD-001" in result.message

    def test_review_idempotent(self, api: RoadmapAPI, setup_db: sqlite3.Connection):
        """review() is idempotent when status matches."""
        setup_db.execute(
            "UPDATE roadmap_items SET status_key = 'review' WHERE id = ?",
            ("ITEM-001",),
        )
        setup_db.commit()

        result = api.review("ITEM-001")
        assert result.success is True
        assert result.data["old_status"] == "review"
        assert result.data["new_status"] == "review"


class TestMyWork:
    """Tests for my_work() - what am I assigned to?"""

    def test_my_work_empty(self, api: RoadmapAPI):
        """my_work() with no assignments."""
        result = api.my_work()
        assert result.success is True
        assert len(result.data) == 0
        # Command points to ready (to find something to claim)
        assert "ready" in result.command.lower()

    def test_my_work_with_assignments(self, api: RoadmapAPI):
        """my_work() shows claimed items."""
        api.claim("ITEM-001")
        api.claim("ITEM-002")
        result = api.my_work()
        assert result.success is True
        assert len(result.data) == 2
        assert "complete" in result.command.lower()


class TestResponseStructure:
    """Tests for RoadmapResponse Pit of Success pattern."""

    def test_success_has_action(self, api: RoadmapAPI):
        """All success responses include next action."""
        result = api.ready()
        assert result.action != ""

    def test_success_has_command(self, api: RoadmapAPI):
        """All success responses include runnable command."""
        result = api.ready()
        assert result.command.startswith("mc ")

    def test_failure_has_recovery_action(self, api: RoadmapAPI):
        """Failure responses include recovery action."""
        result = api.claim("DOES-NOT-EXIST")
        assert result.success is False
        assert result.action != ""
        assert result.command != ""

    def test_blockers_list_formatted(self, api: RoadmapAPI):
        """Blocked items include formatted blocker list."""
        result = api.claim("BLOCKED-001")
        assert len(result.blockers) > 0
        # Blockers should be human-readable
        assert any(":" in b for b in result.blockers)
