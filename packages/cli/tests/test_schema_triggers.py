from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from motus.core.migrations_schema import _apply_audit_columns, parse_migration_file


MIGRATIONS_DIR = Path(__file__).parent.parent / "migrations"


def _apply_all_migrations(conn: sqlite3.Connection) -> None:
    for migration_path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        migration = parse_migration_file(migration_path)
        if migration.up_sql.strip():
            conn.executescript(migration.up_sql)
        if migration.name == "add_audit_columns":
            _apply_audit_columns(conn)


@pytest.fixture
def migrated_db(tmp_path: Path) -> sqlite3.Connection:
    db_path = tmp_path / "schema_triggers.db"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    _apply_all_migrations(conn)
    yield conn
    conn.close()


def _seed_program_product_feature(conn: sqlite3.Connection) -> None:
    conn.execute(
        "INSERT INTO programs (id, name) VALUES ('prog-1', 'Program')"
    )
    conn.execute(
        "INSERT INTO products (id, program_id, name) "
        "VALUES ('prod-1', 'prog-1', 'Product')"
    )
    conn.execute(
        "INSERT INTO features (id, product_id, name) "
        "VALUES ('feat-1', 'prod-1', 'Feature')"
    )


def _insert_roadmap_item(
    conn: sqlite3.Connection,
    item_id: str,
    status_key: str = "pending",
) -> None:
    conn.execute(
        "INSERT INTO roadmap_items (id, phase_key, title, status_key) "
        "VALUES (?, 'phase_a', ?, ?)",
        (item_id, f"Title {item_id}", status_key),
    )


def _insert_attempt(
    conn: sqlite3.Connection,
    attempt_id: str,
    work_id: str,
    *,
    handoff_from_attempt_id: str | None = None,
    handoff_reason: str | None = None,
) -> None:
    conn.execute(
        """
        INSERT INTO attempts (
            id, work_id, worker_id, worker_type,
            handoff_from_attempt_id, handoff_reason
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            attempt_id,
            work_id,
            "agent:test",
            "agent",
            handoff_from_attempt_id,
            handoff_reason,
        ),
    )


def test_audit_log_triggers_block_update_delete(migrated_db) -> None:
    conn = migrated_db
    conn.execute(
        "INSERT INTO audit_log (event_type, actor, action, instance_id) "
        "VALUES ('test', 'system', 'create', 'instance')"
    )
    conn.commit()

    with pytest.raises(
        sqlite3.IntegrityError, match="Audit log entries are immutable"
    ):
        conn.execute(
            "UPDATE audit_log SET action = 'update' WHERE event_type = 'test'"
        )
    conn.rollback()

    with pytest.raises(
        sqlite3.IntegrityError, match="Audit log entries cannot be deleted"
    ):
        conn.execute("DELETE FROM audit_log WHERE event_type = 'test'")
    conn.rollback()


def test_health_check_cleanup_trigger(migrated_db) -> None:
    conn = migrated_db
    conn.execute(
        "INSERT INTO health_check_results (check_name, status, checked_at) "
        "VALUES ('old', 'pass', datetime('now', '-8 days'))"
    )
    conn.execute(
        "INSERT INTO health_check_results (check_name, status) "
        "VALUES ('new', 'pass')"
    )
    row = conn.execute(
        "SELECT COUNT(*) as count FROM health_check_results "
        "WHERE check_name = 'old'"
    ).fetchone()
    assert row["count"] == 0


def test_compliance_triggers_block_update_delete(migrated_db) -> None:
    conn = migrated_db
    conn.execute(
        "INSERT INTO standards "
        "(id, name, level_key, check_type_key, failure_message) "
        "VALUES ('STD-1', 'Standard', 'product', 'boolean', 'fail')"
    )
    conn.execute(
        "INSERT INTO compliance_results "
        "(standard_id, entity_type, entity_id, result, checked_by) "
        "VALUES ('STD-1', 'product', 'prod-1', 'pass', 'system')"
    )
    conn.commit()

    with pytest.raises(
        sqlite3.IntegrityError, match="Compliance results are immutable"
    ):
        conn.execute(
            "UPDATE compliance_results SET result = 'fail' "
            "WHERE entity_id = 'prod-1'"
        )
    conn.rollback()

    with pytest.raises(
        sqlite3.IntegrityError, match="Compliance results cannot be deleted"
    ):
        conn.execute("DELETE FROM compliance_results WHERE entity_id = 'prod-1'")
    conn.rollback()


def test_charter_singleton_enforce_deactivates_previous(migrated_db) -> None:
    conn = migrated_db
    conn.execute(
        "INSERT INTO charter_docs "
        "(id, doc_type_key, version, title, content_hash, is_active) "
        "VALUES ('charter-1', 'roadmap', '1', 'Roadmap v1', 'hash-1', 1)"
    )
    conn.execute(
        "INSERT INTO charter_docs "
        "(id, doc_type_key, version, title, content_hash, is_active) "
        "VALUES ('charter-2', 'roadmap', '2', 'Roadmap v2', 'hash-2', 1)"
    )
    rows = conn.execute(
        "SELECT id, is_active FROM charter_docs "
        "WHERE doc_type_key = 'roadmap' ORDER BY id"
    ).fetchall()
    assert [row["is_active"] for row in rows] == [0, 1]


def test_entity_versions_triggers_block_update_delete(migrated_db) -> None:
    conn = migrated_db
    conn.execute(
        "INSERT INTO entity_versions "
        "(entity_type, entity_id, version, data, changed_by) "
        "VALUES ('product', 'prod-1', 1, '{}', 'system')"
    )
    conn.commit()

    with pytest.raises(
        sqlite3.IntegrityError, match="Entity version history is immutable"
    ):
        conn.execute(
            "UPDATE entity_versions SET data = '{}' WHERE entity_id = 'prod-1'"
        )
    conn.rollback()

    with pytest.raises(
        sqlite3.IntegrityError,
        match="Entity version history cannot be deleted",
    ):
        conn.execute("DELETE FROM entity_versions WHERE entity_id = 'prod-1'")
    conn.rollback()


def test_cr_version_capture_trigger(migrated_db) -> None:
    conn = migrated_db
    conn.execute(
        "INSERT INTO change_requests (id, title) "
        "VALUES ('CR-1', 'Initial')"
    )
    conn.commit()

    conn.execute(
        "UPDATE change_requests SET title = 'Updated', "
        "updated_at = '2099-01-01 00:00:00' "
        "WHERE id = 'CR-1'"
    )
    row = conn.execute(
        "SELECT COUNT(*) as count FROM entity_versions "
        "WHERE entity_type = 'cr' AND entity_id = 'CR-1'"
    ).fetchone()
    assert row["count"] == 1


def test_product_version_capture_trigger(migrated_db) -> None:
    conn = migrated_db
    _seed_program_product_feature(conn)
    conn.commit()

    conn.execute(
        "UPDATE products SET name = 'Product v2', "
        "updated_at = '2099-01-01 00:00:00' "
        "WHERE id = 'prod-1'"
    )
    row = conn.execute(
        "SELECT COUNT(*) as count FROM entity_versions "
        "WHERE entity_type = 'product' AND entity_id = 'prod-1'"
    ).fetchone()
    assert row["count"] == 1


def test_feature_version_capture_trigger(migrated_db) -> None:
    conn = migrated_db
    _seed_program_product_feature(conn)
    conn.commit()

    conn.execute(
        "UPDATE features SET name = 'Feature v2', "
        "updated_at = '2099-01-01 00:00:00' "
        "WHERE id = 'feat-1'"
    )
    row = conn.execute(
        "SELECT COUNT(*) as count FROM entity_versions "
        "WHERE entity_type = 'feature' AND entity_id = 'feat-1'"
    ).fetchone()
    assert row["count"] == 1


def test_bug_version_capture_trigger(migrated_db) -> None:
    conn = migrated_db
    _seed_program_product_feature(conn)
    conn.execute(
        "INSERT INTO bugs (id, title, feature_id, feature_version) "
        "VALUES ('BUG-1', 'Bug', 'feat-1', '1.0')"
    )
    conn.commit()

    conn.execute(
        "UPDATE bugs SET title = 'Bug v2', "
        "updated_at = '2099-01-01 00:00:00' "
        "WHERE id = 'BUG-1'"
    )
    row = conn.execute(
        "SELECT COUNT(*) as count FROM entity_versions "
        "WHERE entity_type = 'bug' AND entity_id = 'BUG-1'"
    ).fetchone()
    assert row["count"] == 1


def test_roadmap_version_capture_trigger(migrated_db) -> None:
    conn = migrated_db
    _insert_roadmap_item(conn, "RI-1")
    conn.commit()

    conn.execute(
        "UPDATE roadmap_items SET title = 'Updated', "
        "updated_at = '2099-01-01 00:00:00' "
        "WHERE id = 'RI-1'"
    )
    row = conn.execute(
        "SELECT COUNT(*) as count FROM entity_versions "
        "WHERE entity_type = 'roadmap_item' AND entity_id = 'RI-1'"
    ).fetchone()
    assert row["count"] == 1


def test_roadmap_dep_no_cycles_trigger(migrated_db) -> None:
    conn = migrated_db
    _insert_roadmap_item(conn, "RI-1")
    _insert_roadmap_item(conn, "RI-2")
    conn.commit()

    conn.execute(
        "INSERT INTO roadmap_dependencies (item_id, depends_on_id) "
        "VALUES ('RI-1', 'RI-2')"
    )
    conn.commit()

    with pytest.raises(
        sqlite3.IntegrityError, match="Circular dependency detected"
    ):
        conn.execute(
            "INSERT INTO roadmap_dependencies (item_id, depends_on_id) "
            "VALUES ('RI-2', 'RI-1')"
        )
    conn.rollback()


def test_roadmap_status_check_deps_trigger(migrated_db) -> None:
    conn = migrated_db
    _insert_roadmap_item(conn, "RI-1")
    _insert_roadmap_item(conn, "RI-2")
    conn.execute(
        "INSERT INTO roadmap_dependencies (item_id, depends_on_id) "
        "VALUES ('RI-2', 'RI-1')"
    )
    conn.commit()

    with pytest.raises(
        sqlite3.IntegrityError,
        match="Cannot start: blocking dependencies not complete",
    ):
        conn.execute(
            "UPDATE roadmap_items SET status_key = 'in_progress' "
            "WHERE id = 'RI-2'"
        )
    conn.rollback()

    conn.execute(
        "UPDATE roadmap_items SET status_key = 'completed' WHERE id = 'RI-1'"
    )
    conn.execute(
        "UPDATE roadmap_items SET status_key = 'in_progress' WHERE id = 'RI-2'"
    )
    row = conn.execute(
        "SELECT status_key FROM roadmap_items WHERE id = 'RI-2'"
    ).fetchone()
    assert row["status_key"] == "in_progress"


def test_roadmap_dependency_audit_trigger(migrated_db) -> None:
    conn = migrated_db
    _insert_roadmap_item(conn, "RI-1")
    _insert_roadmap_item(conn, "RI-2")
    conn.commit()

    conn.execute(
        "INSERT INTO roadmap_dependencies (item_id, depends_on_id, created_by) "
        "VALUES ('RI-2', 'RI-1', 'system')"
    )
    row = conn.execute(
        "SELECT event_type, resource_id FROM audit_log "
        "WHERE event_type = 'roadmap_dependency'"
    ).fetchone()
    assert row["event_type"] == "roadmap_dependency"
    assert row["resource_id"] == "RI-2->RI-1"


def test_roadmap_assignment_audit_and_cascade_triggers(migrated_db) -> None:
    conn = migrated_db
    _insert_roadmap_item(conn, "RI-1")
    _insert_roadmap_item(conn, "RI-2")
    conn.execute(
        "INSERT INTO roadmap_dependencies (item_id, depends_on_id) "
        "VALUES ('RI-2', 'RI-1')"
    )
    conn.commit()

    conn.execute(
        "INSERT INTO roadmap_assignments (item_id, agent_id, assigned_by) "
        "VALUES ('RI-2', 'agent:test', 'system')"
    )
    assignment_id = conn.execute(
        "SELECT id FROM roadmap_assignments WHERE item_id = 'RI-2'"
    ).fetchone()["id"]
    prereq_row = conn.execute(
        "SELECT prerequisite_item_id FROM assignment_prerequisites "
        "WHERE source_assignment_id = ?",
        (assignment_id,),
    ).fetchone()
    assert prereq_row["prerequisite_item_id"] == "RI-1"

    audit_events = {
        row["event_type"]
        for row in conn.execute(
            "SELECT event_type FROM audit_log "
            "WHERE event_type IN ('roadmap_assignment', 'assignment_cascade')"
        ).fetchall()
    }
    assert "roadmap_assignment" in audit_events
    assert "assignment_cascade" in audit_events


def test_roadmap_prereq_resolved_trigger(migrated_db) -> None:
    conn = migrated_db
    _insert_roadmap_item(conn, "RI-1")
    _insert_roadmap_item(conn, "RI-2")
    conn.execute(
        "INSERT INTO roadmap_dependencies (item_id, depends_on_id) "
        "VALUES ('RI-2', 'RI-1')"
    )
    conn.commit()

    conn.execute(
        "INSERT INTO roadmap_assignments (item_id, agent_id) "
        "VALUES ('RI-2', 'agent:test')"
    )
    conn.commit()

    conn.execute(
        "INSERT INTO roadmap_assignments (item_id, agent_id) "
        "VALUES ('RI-1', 'agent:prereq')"
    )
    row = conn.execute(
        "SELECT resolved_at FROM assignment_prerequisites "
        "WHERE prerequisite_item_id = 'RI-1'"
    ).fetchone()
    assert row["resolved_at"] is not None


def test_kernel_decisions_immutable(migrated_db) -> None:
    conn = migrated_db
    conn.execute(
        "INSERT INTO kernel_decisions "
        "(id, decision_type, decision_summary, decided_by) "
        "VALUES ('KD-1', 'approval', 'ok', 'system')"
    )
    conn.commit()

    with pytest.raises(
        sqlite3.IntegrityError,
        match="KERNEL: Decision records are immutable",
    ):
        conn.execute(
            "UPDATE kernel_decisions SET decision_summary = 'nope' "
            "WHERE id = 'KD-1'"
        )
    conn.rollback()

    with pytest.raises(
        sqlite3.IntegrityError,
        match="KERNEL: Decision records cannot be deleted",
    ):
        conn.execute("DELETE FROM kernel_decisions WHERE id = 'KD-1'")
    conn.rollback()


def test_kernel_evidence_immutable(migrated_db) -> None:
    conn = migrated_db
    conn.execute(
        "INSERT INTO kernel_evidence "
        "(id, evidence_type, created_by) "
        "VALUES ('KE-1', 'test_result', 'system')"
    )
    conn.commit()

    with pytest.raises(
        sqlite3.IntegrityError,
        match="KERNEL: Evidence records are immutable",
    ):
        conn.execute(
            "UPDATE kernel_evidence SET title = 'nope' WHERE id = 'KE-1'"
        )
    conn.rollback()

    with pytest.raises(
        sqlite3.IntegrityError,
        match="KERNEL: Evidence records cannot be deleted",
    ):
        conn.execute("DELETE FROM kernel_evidence WHERE id = 'KE-1'")
    conn.rollback()


def test_kernel_outcomes_immutable(migrated_db) -> None:
    conn = migrated_db
    conn.execute(
        "INSERT INTO kernel_outcomes "
        "(id, outcome_type, created_by) "
        "VALUES ('KO-1', 'schema', 'system')"
    )
    conn.commit()

    with pytest.raises(
        sqlite3.IntegrityError,
        match="KERNEL: Outcome records are immutable",
    ):
        conn.execute(
            "UPDATE kernel_outcomes SET description = 'nope' "
            "WHERE id = 'KO-1'"
        )
    conn.rollback()

    with pytest.raises(
        sqlite3.IntegrityError,
        match="KERNEL: Outcome records cannot be deleted",
    ):
        conn.execute("DELETE FROM kernel_outcomes WHERE id = 'KO-1'")
    conn.rollback()


def test_attempts_no_double_claim_trigger(migrated_db) -> None:
    conn = migrated_db
    _insert_roadmap_item(conn, "RI-ATT-1")
    _insert_attempt(conn, "ATT-1", "RI-ATT-1")
    conn.commit()

    with pytest.raises(
        sqlite3.IntegrityError,
        match="KERNEL: Work already has active attempt",
    ):
        _insert_attempt(conn, "ATT-2", "RI-ATT-1")
    conn.rollback()


def test_attempts_no_claim_blocked_trigger(migrated_db) -> None:
    conn = migrated_db
    _insert_roadmap_item(conn, "RI-ATT-2")
    conn.execute(
        """
        INSERT INTO blockers (id, work_id, reason_code, title, created_by)
        VALUES ('BLK-1', 'RI-ATT-2', 'missing_dependency', 'Blocked', 'system')
        """
    )
    conn.commit()

    with pytest.raises(
        sqlite3.IntegrityError,
        match="KERNEL: Work has unresolved blockers",
    ):
        _insert_attempt(conn, "ATT-3", "RI-ATT-2")
    conn.rollback()


def test_attempts_handoff_requires_reason(migrated_db) -> None:
    conn = migrated_db
    _insert_roadmap_item(conn, "RI-ATT-3")
    _insert_attempt(conn, "ATT-4", "RI-ATT-3")
    conn.commit()

    with pytest.raises(
        sqlite3.IntegrityError,
        match="KERNEL: Handoff requires explanation",
    ):
        _insert_attempt(
            conn,
            "ATT-5",
            "RI-ATT-3",
            handoff_from_attempt_id="ATT-4",
        )
    conn.rollback()


def test_attempts_completion_requires_evidence(migrated_db) -> None:
    conn = migrated_db
    _insert_roadmap_item(conn, "RI-ATT-4")
    _insert_attempt(conn, "ATT-6", "RI-ATT-4")
    conn.commit()

    with pytest.raises(
        sqlite3.IntegrityError,
        match="KERNEL: Cannot mark attempt completed without evidence",
    ):
        conn.execute("UPDATE attempts SET outcome = 'completed' WHERE id = 'ATT-6'")
    conn.rollback()

    conn.execute(
        """
        INSERT INTO evidence (
            id, work_id, attempt_id, evidence_type, uri, sha256, created_by
        )
        VALUES ('EV-1', 'RI-ATT-4', 'ATT-6', 'log', 'file://log', 'abc', 'system')
        """
    )
    conn.execute("UPDATE attempts SET outcome = 'completed' WHERE id = 'ATT-6'")
    row = conn.execute(
        "SELECT outcome FROM attempts WHERE id = 'ATT-6'"
    ).fetchone()
    assert row["outcome"] == "completed"


def test_attempts_blocked_requires_blocker(migrated_db) -> None:
    conn = migrated_db
    _insert_roadmap_item(conn, "RI-ATT-5")
    _insert_attempt(conn, "ATT-7", "RI-ATT-5")
    conn.commit()

    with pytest.raises(
        sqlite3.IntegrityError,
        match="KERNEL: Cannot mark attempt blocked without blocker record",
    ):
        conn.execute("UPDATE attempts SET outcome = 'blocked' WHERE id = 'ATT-7'")
    conn.rollback()

    conn.execute(
        """
        INSERT INTO blockers (
            id, work_id, attempt_id, reason_code, title, created_by
        )
        VALUES ('BLK-2', 'RI-ATT-5', 'ATT-7', 'missing_info', 'Need info', 'system')
        """
    )
    conn.execute("UPDATE attempts SET outcome = 'blocked' WHERE id = 'ATT-7'")
    row = conn.execute(
        "SELECT outcome FROM attempts WHERE id = 'ATT-7'"
    ).fetchone()
    assert row["outcome"] == "blocked"


def test_decisions_immutable(migrated_db) -> None:
    conn = migrated_db
    _insert_roadmap_item(conn, "RI-DEC-1")
    conn.execute(
        """
        INSERT INTO decisions (id, work_id, decision_type, decided_by)
        VALUES ('DEC-1', 'RI-DEC-1', 'approval', 'system')
        """
    )
    conn.commit()

    with pytest.raises(
        sqlite3.IntegrityError,
        match="KERNEL: Decision records are immutable",
    ):
        conn.execute(
            "UPDATE decisions SET decision_summary = 'nope' WHERE id = 'DEC-1'"
        )
    conn.rollback()

    with pytest.raises(
        sqlite3.IntegrityError,
        match="KERNEL: Decision records cannot be deleted",
    ):
        conn.execute("DELETE FROM decisions WHERE id = 'DEC-1'")
    conn.rollback()


def test_evidence_immutable(migrated_db) -> None:
    conn = migrated_db
    _insert_roadmap_item(conn, "RI-EV-1")
    conn.execute(
        """
        INSERT INTO evidence (
            id, work_id, evidence_type, uri, sha256, created_by
        )
        VALUES ('EV-2', 'RI-EV-1', 'log', 'file://log', 'abc', 'system')
        """
    )
    conn.commit()

    with pytest.raises(
        sqlite3.IntegrityError,
        match="KERNEL: Evidence records are immutable",
    ):
        conn.execute(
            "UPDATE evidence SET title = 'nope' WHERE id = 'EV-2'"
        )
    conn.rollback()

    with pytest.raises(
        sqlite3.IntegrityError,
        match="KERNEL: Evidence records cannot be deleted",
    ):
        conn.execute("DELETE FROM evidence WHERE id = 'EV-2'")
    conn.rollback()


def test_blockers_resolution_immutable(migrated_db) -> None:
    conn = migrated_db
    _insert_roadmap_item(conn, "RI-BLK-1")
    conn.execute(
        """
        INSERT INTO blockers (
            id, work_id, reason_code, title, created_by,
            resolved_at, resolved_by, resolution
        )
        VALUES (
            'BLK-3', 'RI-BLK-1', 'missing_info', 'Need info', 'system',
            '2025-01-01 00:00:00', 'system', 'done'
        )
        """
    )
    conn.commit()

    with pytest.raises(
        sqlite3.IntegrityError,
        match="KERNEL: Blocker resolution is immutable",
    ):
        conn.execute(
            "UPDATE blockers SET resolution = 'changed' WHERE id = 'BLK-3'"
        )
    conn.rollback()


def test_blockers_resolution_requires_resolution(migrated_db) -> None:
    conn = migrated_db
    _insert_roadmap_item(conn, "RI-BLK-2")
    conn.execute(
        """
        INSERT INTO blockers (id, work_id, reason_code, title, created_by)
        VALUES ('BLK-4', 'RI-BLK-2', 'missing_info', 'Need info', 'system')
        """
    )
    conn.commit()

    with pytest.raises(
        sqlite3.IntegrityError,
        match="KERNEL: Blocker resolution requires explanation in resolution field",
    ):
        conn.execute(
            "UPDATE blockers SET resolved_at = datetime('now') WHERE id = 'BLK-4'"
        )
    conn.rollback()


def test_blockers_resolution_requires_evidence_or_waiver(migrated_db) -> None:
    conn = migrated_db
    _insert_roadmap_item(conn, "RI-BLK-3")
    conn.execute(
        """
        INSERT INTO blockers (id, work_id, reason_code, title, created_by)
        VALUES ('BLK-5', 'RI-BLK-3', 'missing_info', 'Need info', 'system')
        """
    )
    conn.commit()

    with pytest.raises(
        sqlite3.IntegrityError,
        match="KERNEL: Blocker resolution requires evidence or waiver decision",
    ):
        conn.execute(
            """
            UPDATE blockers
            SET resolved_at = datetime('now'),
                resolution = 'done'
            WHERE id = 'BLK-5'
            """
        )
    conn.rollback()


def test_blockers_resolution_with_evidence_succeeds(migrated_db) -> None:
    conn = migrated_db
    _insert_roadmap_item(conn, "RI-BLK-4")
    conn.execute(
        """
        INSERT INTO blockers (
            id, work_id, reason_code, title, created_by, created_at
        )
        VALUES (
            'BLK-6', 'RI-BLK-4', 'missing_info', 'Need info', 'system',
            datetime('now', '-1 hour')
        )
        """
    )
    conn.execute(
        """
        INSERT INTO evidence (
            id, work_id, evidence_type, uri, sha256, created_by
        )
        VALUES ('EV-3', 'RI-BLK-4', 'log', 'file://log', 'abc', 'system')
        """
    )
    conn.execute(
        """
        UPDATE blockers
        SET resolved_at = datetime('now'),
            resolved_by = 'system',
            resolution = 'resolved'
        WHERE id = 'BLK-6'
        """
    )
    row = conn.execute(
        "SELECT resolved_at FROM blockers WHERE id = 'BLK-6'"
    ).fetchone()
    assert row["resolved_at"] is not None
