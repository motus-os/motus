"""Comprehensive tests for roadmap dependency management.

Tests cover:
1. Basic CRUD operations
2. Dependency validation (no cycles)
3. Status transitions with dependencies
4. Assignment management
5. Ordering/ranking
6. Views and queries
"""

import sqlite3
import pytest
from pathlib import Path


@pytest.fixture
def db_with_roadmap(tmp_path):
    """Create a test database with roadmap schema."""
    db_path = tmp_path / "test_roadmap.db"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    # Apply base schema (simplified for testing)
    conn.executescript("""
        -- Base tables needed
        CREATE TABLE instance_config (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        INSERT INTO instance_config (key, value) VALUES ('instance_id', 'test-instance');

        CREATE TABLE audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT NOT NULL,
            actor TEXT NOT NULL,
            resource_type TEXT,
            resource_id TEXT,
            action TEXT NOT NULL,
            old_value TEXT,
            new_value TEXT,
            instance_id TEXT NOT NULL
        );

        CREATE TABLE terminology (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            domain TEXT NOT NULL,
            internal_key TEXT NOT NULL,
            display_name TEXT NOT NULL,
            UNIQUE(domain, internal_key)
        );

        -- Insert roadmap terminology
        INSERT INTO terminology (domain, internal_key, display_name) VALUES
        ('roadmap_phase', 'phase_a', 'Phase A'),
        ('roadmap_phase', 'phase_b', 'Phase B'),
        ('roadmap_phase', 'phase_c', 'Phase C'),
        ('roadmap_status', 'pending', 'Pending'),
        ('roadmap_status', 'in_progress', 'In Progress'),
        ('roadmap_status', 'blocked', 'Blocked'),
        ('roadmap_status', 'completed', 'Completed');

        -- Roadmap items table (without rank - migration adds it)
        CREATE TABLE roadmap_items (
            id TEXT PRIMARY KEY,
            phase_key TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            status_key TEXT NOT NULL DEFAULT 'pending',
            owner TEXT,
            target_date TEXT,
            completed_at TEXT,
            sort_order INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            deleted_at TEXT
        );
    """)

    # Apply migration 007 (roadmap dependencies)
    migration_path = Path(__file__).parent.parent / "migrations" / "007_roadmap_dependencies.sql"
    if migration_path.exists():
        migration_sql = migration_path.read_text()
        # Extract UP section only
        up_section = migration_sql.split("-- DOWN")[0]
        # Remove comments that might cause issues
        lines = [line for line in up_section.split("\n")
                 if not line.strip().startswith("--") or line.strip().startswith("--")]
        conn.executescript(up_section)

    yield conn
    conn.close()


@pytest.fixture
def populated_db(db_with_roadmap):
    """Database with some test roadmap items."""
    conn = db_with_roadmap

    # Insert test items
    conn.executescript("""
        INSERT INTO roadmap_items (id, phase_key, title, status_key, rank) VALUES
        ('RI-001', 'phase_a', 'Foundation work', 'completed', 1.0),
        ('RI-002', 'phase_a', 'Core API', 'completed', 2.0),
        ('RI-003', 'phase_b', 'Feature X', 'pending', 1.0),
        ('RI-004', 'phase_b', 'Feature Y', 'pending', 2.0),
        ('RI-005', 'phase_c', 'Testing', 'pending', 1.0);
    """)
    conn.commit()

    return conn


class TestRoadmapDependencies:
    """Test roadmap_dependencies table operations."""

    def test_create_dependency(self, populated_db):
        """Can create a valid dependency."""
        conn = populated_db

        conn.execute("""
            INSERT INTO roadmap_dependencies (item_id, depends_on_id, dependency_type)
            VALUES ('RI-003', 'RI-002', 'blocks')
        """)
        conn.commit()

        result = conn.execute(
            "SELECT * FROM roadmap_dependencies WHERE item_id = 'RI-003'"
        ).fetchone()

        assert result is not None
        assert result['depends_on_id'] == 'RI-002'
        assert result['dependency_type'] == 'blocks'

    def test_cannot_depend_on_self(self, populated_db):
        """Cannot create self-referential dependency."""
        conn = populated_db

        # Either CHECK constraint or cycle detector will catch this
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("""
                INSERT INTO roadmap_dependencies (item_id, depends_on_id)
                VALUES ('RI-003', 'RI-003')
            """)

    def test_detect_direct_cycle(self, populated_db):
        """Detects direct circular dependency (A->B, B->A)."""
        conn = populated_db

        # First dependency: RI-003 depends on RI-004
        conn.execute("""
            INSERT INTO roadmap_dependencies (item_id, depends_on_id)
            VALUES ('RI-003', 'RI-004')
        """)
        conn.commit()

        # Try to create reverse: RI-004 depends on RI-003 (cycle!)
        with pytest.raises(sqlite3.IntegrityError, match="Circular dependency"):
            conn.execute("""
                INSERT INTO roadmap_dependencies (item_id, depends_on_id)
                VALUES ('RI-004', 'RI-003')
            """)

    def test_detect_indirect_cycle(self, populated_db):
        """Detects indirect circular dependency (A->B->C->A)."""
        conn = populated_db

        # Create chain: RI-005 -> RI-004 -> RI-003
        conn.execute("""
            INSERT INTO roadmap_dependencies (item_id, depends_on_id) VALUES
            ('RI-005', 'RI-004'),
            ('RI-004', 'RI-003')
        """)
        conn.commit()

        # Try to complete cycle: RI-003 -> RI-005 (cycle!)
        with pytest.raises(sqlite3.IntegrityError, match="Circular dependency"):
            conn.execute("""
                INSERT INTO roadmap_dependencies (item_id, depends_on_id)
                VALUES ('RI-003', 'RI-005')
            """)

    def test_multiple_dependencies(self, populated_db):
        """Item can have multiple dependencies."""
        conn = populated_db

        conn.execute("""
            INSERT INTO roadmap_dependencies (item_id, depends_on_id) VALUES
            ('RI-005', 'RI-001'),
            ('RI-005', 'RI-002'),
            ('RI-005', 'RI-003')
        """)
        conn.commit()

        count = conn.execute(
            "SELECT COUNT(*) FROM roadmap_dependencies WHERE item_id = 'RI-005'"
        ).fetchone()[0]

        assert count == 3


class TestStatusTransitions:
    """Test status transitions with dependency validation."""

    def test_can_start_with_completed_deps(self, populated_db):
        """Can start item if all blocking deps are completed."""
        conn = populated_db

        # RI-003 depends on RI-002 (which is completed)
        conn.execute("""
            INSERT INTO roadmap_dependencies (item_id, depends_on_id, dependency_type)
            VALUES ('RI-003', 'RI-002', 'blocks')
        """)
        conn.commit()

        # Should succeed - RI-002 is completed
        conn.execute("""
            UPDATE roadmap_items SET status_key = 'in_progress'
            WHERE id = 'RI-003'
        """)
        conn.commit()

        status = conn.execute(
            "SELECT status_key FROM roadmap_items WHERE id = 'RI-003'"
        ).fetchone()[0]

        assert status == 'in_progress'

    def test_cannot_start_with_pending_deps(self, populated_db):
        """Cannot start item if blocking deps are not completed."""
        conn = populated_db

        # RI-005 depends on RI-003 (which is pending)
        conn.execute("""
            INSERT INTO roadmap_dependencies (item_id, depends_on_id, dependency_type)
            VALUES ('RI-005', 'RI-003', 'blocks')
        """)
        conn.commit()

        # Should fail - RI-003 is not completed
        with pytest.raises(sqlite3.IntegrityError, match="blocking dependencies not complete"):
            conn.execute("""
                UPDATE roadmap_items SET status_key = 'in_progress'
                WHERE id = 'RI-005'
            """)

    def test_soft_deps_dont_block(self, populated_db):
        """Soft dependencies don't block status transition."""
        conn = populated_db

        # RI-005 has soft dep on RI-003 (pending)
        conn.execute("""
            INSERT INTO roadmap_dependencies (item_id, depends_on_id, dependency_type)
            VALUES ('RI-005', 'RI-003', 'soft')
        """)
        conn.commit()

        # Should succeed - soft deps don't block
        conn.execute("""
            UPDATE roadmap_items SET status_key = 'in_progress'
            WHERE id = 'RI-005'
        """)
        conn.commit()

        status = conn.execute(
            "SELECT status_key FROM roadmap_items WHERE id = 'RI-005'"
        ).fetchone()[0]

        assert status == 'in_progress'


class TestAssignments:
    """Test roadmap_assignments table operations."""

    def test_create_assignment(self, populated_db):
        """Can create an assignment."""
        conn = populated_db

        conn.execute("""
            INSERT INTO roadmap_assignments (item_id, agent_id, role, assigned_by)
            VALUES ('RI-003', 'agent:builder-haiku', 'implementer', 'user:ben')
        """)
        conn.commit()

        result = conn.execute(
            "SELECT * FROM roadmap_assignments WHERE item_id = 'RI-003'"
        ).fetchone()

        assert result is not None
        assert result['agent_id'] == 'agent:builder-haiku'
        assert result['role'] == 'implementer'
        assert result['status'] == 'assigned'

    def test_multiple_agents_same_item(self, populated_db):
        """Multiple agents can be assigned to same item with different roles."""
        conn = populated_db

        conn.execute("""
            INSERT INTO roadmap_assignments (item_id, agent_id, role) VALUES
            ('RI-003', 'agent:builder-haiku', 'implementer'),
            ('RI-003', 'agent:opus-main', 'reviewer'),
            ('RI-003', 'user:ben', 'owner')
        """)
        conn.commit()

        count = conn.execute(
            "SELECT COUNT(*) FROM roadmap_assignments WHERE item_id = 'RI-003'"
        ).fetchone()[0]

        assert count == 3

    def test_no_duplicate_role(self, populated_db):
        """Same agent can't have same role twice on same item."""
        conn = populated_db

        conn.execute("""
            INSERT INTO roadmap_assignments (item_id, agent_id, role)
            VALUES ('RI-003', 'agent:builder-haiku', 'implementer')
        """)
        conn.commit()

        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("""
                INSERT INTO roadmap_assignments (item_id, agent_id, role)
                VALUES ('RI-003', 'agent:builder-haiku', 'implementer')
            """)


class TestOrdering:
    """Test ranking/ordering functionality."""

    def test_fractional_ranking(self, populated_db):
        """Can insert between existing ranks using fractional values."""
        conn = populated_db

        # Insert between RI-003 (rank 1.0) and RI-004 (rank 2.0)
        conn.execute("""
            INSERT INTO roadmap_items (id, phase_key, title, status_key, rank)
            VALUES ('RI-006', 'phase_b', 'New Feature', 'pending', 1.5)
        """)
        conn.commit()

        items = conn.execute("""
            SELECT id, rank FROM roadmap_items
            WHERE phase_key = 'phase_b' AND deleted_at IS NULL
            ORDER BY rank
        """).fetchall()

        assert [r['id'] for r in items] == ['RI-003', 'RI-006', 'RI-004']

    def test_next_rank_view(self, populated_db):
        """v_next_rank provides correct next rank for phase."""
        conn = populated_db

        result = conn.execute("""
            SELECT * FROM v_next_rank WHERE phase_key = 'phase_b'
        """).fetchone()

        # phase_b has max rank 2.0, so next should be 3.0
        assert result['next_rank'] == 3.0


class TestViews:
    """Test query views."""

    def test_blocked_items_view(self, populated_db):
        """v_blocked_items shows items with unmet dependencies."""
        conn = populated_db

        # RI-005 depends on RI-003 (pending)
        conn.execute("""
            INSERT INTO roadmap_dependencies (item_id, depends_on_id, dependency_type)
            VALUES ('RI-005', 'RI-003', 'blocks')
        """)
        conn.commit()

        blocked = conn.execute("SELECT * FROM v_blocked_items").fetchall()

        assert len(blocked) == 1
        assert blocked[0]['id'] == 'RI-005'
        assert blocked[0]['blocking_count'] == 1

    def test_ready_items_view(self, populated_db):
        """v_ready_items shows items that can start."""
        conn = populated_db

        # RI-003 has no deps, should be ready
        # RI-005 depends on RI-003 (pending), should NOT be ready
        conn.execute("""
            INSERT INTO roadmap_dependencies (item_id, depends_on_id, dependency_type)
            VALUES ('RI-005', 'RI-003', 'blocks')
        """)
        conn.commit()

        ready = conn.execute("SELECT id FROM v_ready_items").fetchall()
        ready_ids = [r['id'] for r in ready]

        assert 'RI-003' in ready_ids
        assert 'RI-004' in ready_ids
        assert 'RI-005' not in ready_ids  # blocked

    def test_dependency_graph_view(self, populated_db):
        """v_dependency_graph shows all dependencies."""
        conn = populated_db

        conn.execute("""
            INSERT INTO roadmap_dependencies (item_id, depends_on_id) VALUES
            ('RI-003', 'RI-001'),
            ('RI-004', 'RI-002'),
            ('RI-005', 'RI-003')
        """)
        conn.commit()

        graph = conn.execute("SELECT * FROM v_dependency_graph").fetchall()

        assert len(graph) == 3


class TestAuditTrail:
    """Test audit logging for roadmap operations."""

    def test_dependency_audited(self, populated_db):
        """Creating dependency is logged to audit_log."""
        conn = populated_db

        conn.execute("""
            INSERT INTO roadmap_dependencies (item_id, depends_on_id, created_by)
            VALUES ('RI-003', 'RI-001', 'user:ben')
        """)
        conn.commit()

        audit = conn.execute("""
            SELECT * FROM audit_log WHERE event_type = 'roadmap_dependency'
        """).fetchone()

        assert audit is not None
        assert audit['actor'] == 'user:ben'
        assert audit['action'] == 'create'

    def test_assignment_audited(self, populated_db):
        """Creating assignment is logged to audit_log."""
        conn = populated_db

        conn.execute("""
            INSERT INTO roadmap_assignments (item_id, agent_id, assigned_by)
            VALUES ('RI-003', 'agent:builder-haiku', 'user:ben')
        """)
        conn.commit()

        audit = conn.execute("""
            SELECT * FROM audit_log WHERE event_type = 'roadmap_assignment'
        """).fetchone()

        assert audit is not None
        assert audit['actor'] == 'user:ben'
        assert audit['action'] == 'assign'


class TestCascadeAutomation:
    """Test dependency cascade automation when assignments are made."""

    def test_prerequisite_chain_view(self, populated_db):
        """v_prerequisite_chain shows full dependency chain."""
        conn = populated_db

        # Create chain: RI-005 -> RI-004 -> RI-003 -> RI-002
        conn.execute("""
            INSERT INTO roadmap_dependencies (item_id, depends_on_id) VALUES
            ('RI-005', 'RI-004'),
            ('RI-004', 'RI-003'),
            ('RI-003', 'RI-002')
        """)
        conn.commit()

        # Query full chain for RI-005
        chain = conn.execute("""
            SELECT prereq_id, depth FROM v_prerequisite_chain
            WHERE root_item_id = 'RI-005'
            ORDER BY depth
        """).fetchall()

        assert len(chain) == 3
        assert chain[0]['prereq_id'] == 'RI-004'  # depth 1
        assert chain[0]['depth'] == 1
        assert chain[1]['prereq_id'] == 'RI-003'  # depth 2
        assert chain[1]['depth'] == 2
        assert chain[2]['prereq_id'] == 'RI-002'  # depth 3
        assert chain[2]['depth'] == 3

    def test_assignment_shows_readiness(self, populated_db):
        """v_assignment_with_prerequisites shows if item is ready."""
        conn = populated_db

        # RI-005 depends on RI-003 (pending)
        conn.execute("""
            INSERT INTO roadmap_dependencies (item_id, depends_on_id, dependency_type)
            VALUES ('RI-005', 'RI-003', 'blocks')
        """)
        conn.commit()

        # Assign agent to RI-005 (blocked) and RI-003 (ready)
        conn.execute("""
            INSERT INTO roadmap_assignments (item_id, agent_id, role) VALUES
            ('RI-005', 'agent:opus', 'implementer'),
            ('RI-003', 'agent:haiku', 'implementer')
        """)
        conn.commit()

        assignments = conn.execute("""
            SELECT item_id, readiness, immediate_blockers
            FROM v_assignment_with_prerequisites
            ORDER BY item_id
        """).fetchall()

        assert len(assignments) == 2

        # RI-003 should be ready (no blocking deps)
        ri003 = [a for a in assignments if a['item_id'] == 'RI-003'][0]
        assert ri003['readiness'] == 'ready'

        # RI-005 should be blocked by RI-003
        ri005 = [a for a in assignments if a['item_id'] == 'RI-005'][0]
        assert ri005['readiness'] == 'blocked'
        assert 'RI-003' in ri005['immediate_blockers']

    def test_assignment_surfaces_unassigned_prereqs(self, populated_db):
        """Assigning blocked item surfaces unassigned prerequisites."""
        conn = populated_db

        # Create chain: RI-005 -> RI-004 -> RI-003
        conn.execute("""
            INSERT INTO roadmap_dependencies (item_id, depends_on_id) VALUES
            ('RI-005', 'RI-004'),
            ('RI-004', 'RI-003')
        """)
        conn.commit()

        # Assign agent to RI-005 (all deps unassigned)
        conn.execute("""
            INSERT INTO roadmap_assignments (item_id, agent_id, assigned_by)
            VALUES ('RI-005', 'agent:opus', 'user:ben')
        """)
        conn.commit()

        # Check assignment_prerequisites table was populated
        prereqs = conn.execute("""
            SELECT prerequisite_item_id, depth
            FROM assignment_prerequisites
            WHERE resolved_at IS NULL
            ORDER BY depth
        """).fetchall()

        assert len(prereqs) == 2
        prereq_ids = [p['prerequisite_item_id'] for p in prereqs]
        assert 'RI-004' in prereq_ids
        assert 'RI-003' in prereq_ids

    def test_cascade_audit_logged(self, populated_db):
        """Assignment with unassigned prerequisites logs cascade event."""
        conn = populated_db

        # RI-005 depends on RI-003 (unassigned)
        conn.execute("""
            INSERT INTO roadmap_dependencies (item_id, depends_on_id)
            VALUES ('RI-005', 'RI-003')
        """)
        conn.commit()

        # Assign agent to RI-005
        conn.execute("""
            INSERT INTO roadmap_assignments (item_id, agent_id, assigned_by)
            VALUES ('RI-005', 'agent:opus', 'user:ben')
        """)
        conn.commit()

        # Check cascade audit event was logged
        audit = conn.execute("""
            SELECT * FROM audit_log
            WHERE event_type = 'assignment_cascade'
        """).fetchone()

        assert audit is not None
        assert audit['action'] == 'cascade_detected'
        assert 'RI-003' in audit['new_value']

    def test_prereq_resolved_when_assigned(self, populated_db):
        """Prerequisites marked resolved when they get assigned."""
        conn = populated_db

        # RI-005 depends on RI-003
        conn.execute("""
            INSERT INTO roadmap_dependencies (item_id, depends_on_id)
            VALUES ('RI-005', 'RI-003')
        """)
        conn.commit()

        # Assign RI-005 first (surfaces RI-003 as unassigned prereq)
        conn.execute("""
            INSERT INTO roadmap_assignments (item_id, agent_id)
            VALUES ('RI-005', 'agent:opus')
        """)
        conn.commit()

        # Verify RI-003 is in unresolved prerequisites
        unresolved = conn.execute("""
            SELECT * FROM assignment_prerequisites
            WHERE prerequisite_item_id = 'RI-003' AND resolved_at IS NULL
        """).fetchone()
        assert unresolved is not None

        # Now assign RI-003
        conn.execute("""
            INSERT INTO roadmap_assignments (item_id, agent_id)
            VALUES ('RI-003', 'agent:haiku')
        """)
        conn.commit()

        # Verify RI-003 is now resolved
        resolved = conn.execute("""
            SELECT * FROM assignment_prerequisites
            WHERE prerequisite_item_id = 'RI-003' AND resolved_at IS NOT NULL
        """).fetchone()
        assert resolved is not None

    def test_unassigned_prerequisites_view(self, populated_db):
        """v_unassigned_prerequisites shows items needing attention."""
        conn = populated_db

        # Create dependencies
        conn.execute("""
            INSERT INTO roadmap_dependencies (item_id, depends_on_id) VALUES
            ('RI-005', 'RI-003'),
            ('RI-004', 'RI-003')
        """)
        conn.commit()

        # Assign RI-005 and RI-004 (both need RI-003)
        conn.execute("""
            INSERT INTO roadmap_assignments (item_id, agent_id) VALUES
            ('RI-005', 'agent:opus'),
            ('RI-004', 'agent:sonnet')
        """)
        conn.commit()

        # Check unassigned prerequisites view
        unassigned = conn.execute("""
            SELECT prerequisite_item_id, blocking_count
            FROM v_unassigned_prerequisites
        """).fetchall()

        assert len(unassigned) == 1
        assert unassigned[0]['prerequisite_item_id'] == 'RI-003'
        assert unassigned[0]['blocking_count'] == 2  # Blocks both RI-004 and RI-005

    def test_no_cascade_for_ready_item(self, populated_db):
        """Assigning ready item doesn't create cascade entries."""
        conn = populated_db

        # RI-003 has no dependencies, is ready
        conn.execute("""
            INSERT INTO roadmap_assignments (item_id, agent_id)
            VALUES ('RI-003', 'agent:haiku')
        """)
        conn.commit()

        # No prerequisites should be surfaced
        prereqs = conn.execute("""
            SELECT * FROM assignment_prerequisites
        """).fetchall()

        assert len(prereqs) == 0

        # No cascade audit event
        cascade_audit = conn.execute("""
            SELECT * FROM audit_log WHERE event_type = 'assignment_cascade'
        """).fetchone()

        assert cascade_audit is None
