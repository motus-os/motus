-- Migration: 007_roadmap_dependencies
-- Version: 7
-- Description: Add dependency management and assignments to roadmap_items
--
-- =============================================================================
-- DESIGN PRINCIPLES
-- =============================================================================
-- 1. DEFENSIVE: All constraints enforced at DB level, not just application
-- 2. DEPENDENCIES: Block start until dependencies complete
-- 3. CYCLE PREVENTION: Trigger validates no circular dependencies
-- 4. ASSIGNMENTS: Track who's working on what with timestamps
-- 5. ORDERING: Fractional ranking allows insertion without reorder
-- =============================================================================

-- UP

-- =============================================================================
-- ROADMAP DEPENDENCIES
-- =============================================================================
-- Tracks what roadmap items depend on other roadmap items.
-- A task cannot start until all its blocking dependencies are complete.

CREATE TABLE IF NOT EXISTS roadmap_dependencies (
    item_id TEXT NOT NULL,
    depends_on_id TEXT NOT NULL,
    dependency_type TEXT NOT NULL DEFAULT 'blocks'
        CHECK (dependency_type IN ('blocks', 'soft', 'related')),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    created_by TEXT,
    notes TEXT,

    PRIMARY KEY (item_id, depends_on_id),
    FOREIGN KEY (item_id) REFERENCES roadmap_items(id),
    FOREIGN KEY (depends_on_id) REFERENCES roadmap_items(id),
    -- Cannot depend on itself
    CHECK (item_id != depends_on_id)
);

CREATE INDEX IF NOT EXISTS idx_roadmap_dep_item ON roadmap_dependencies(item_id);
CREATE INDEX IF NOT EXISTS idx_roadmap_dep_depends ON roadmap_dependencies(depends_on_id);

-- =============================================================================
-- ROADMAP ASSIGNMENTS
-- =============================================================================
-- Tracks who is assigned to work on a roadmap item.
-- Multiple agents can be assigned to the same item.

CREATE TABLE IF NOT EXISTS roadmap_assignments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id TEXT NOT NULL,
    agent_id TEXT NOT NULL,         -- 'agent:builder-haiku', 'user:ben', 'agent:opus-main'
    role TEXT NOT NULL DEFAULT 'implementer'
        CHECK (role IN ('implementer', 'reviewer', 'owner', 'observer')),
    assigned_at TEXT NOT NULL DEFAULT (datetime('now')),
    assigned_by TEXT,
    started_at TEXT,                -- When agent actually started
    completed_at TEXT,              -- When agent finished their part
    status TEXT NOT NULL DEFAULT 'assigned'
        CHECK (status IN ('assigned', 'active', 'completed', 'dropped')),
    notes TEXT,

    FOREIGN KEY (item_id) REFERENCES roadmap_items(id),
    UNIQUE (item_id, agent_id, role)
);

CREATE INDEX IF NOT EXISTS idx_assignment_item ON roadmap_assignments(item_id);
CREATE INDEX IF NOT EXISTS idx_assignment_agent ON roadmap_assignments(agent_id);
CREATE INDEX IF NOT EXISTS idx_assignment_status ON roadmap_assignments(status) WHERE status = 'active';

-- =============================================================================
-- ORDERING: Add fractional rank column
-- =============================================================================
-- Allows insertion between items without reordering all items
-- Example: Insert between rank 1.0 and 2.0 = rank 1.5

ALTER TABLE roadmap_items ADD COLUMN rank REAL;

-- Initialize rank from sort_order for existing items
UPDATE roadmap_items SET rank = CAST(sort_order AS REAL) WHERE rank IS NULL;

CREATE INDEX IF NOT EXISTS idx_roadmap_rank ON roadmap_items(phase_key, rank) WHERE deleted_at IS NULL;

-- =============================================================================
-- DEPENDENCY VALIDATION VIEWS
-- =============================================================================

-- View: Items with unmet blocking dependencies
CREATE VIEW IF NOT EXISTS v_blocked_items AS
SELECT
    ri.id,
    ri.title,
    ri.phase_key,
    ri.status_key,
    COUNT(rd.depends_on_id) as blocking_count,
    GROUP_CONCAT(rd.depends_on_id, ', ') as blocking_items
FROM roadmap_items ri
JOIN roadmap_dependencies rd ON rd.item_id = ri.id AND rd.dependency_type = 'blocks'
JOIN roadmap_items dep ON dep.id = rd.depends_on_id
WHERE ri.deleted_at IS NULL
  AND ri.status_key NOT IN ('completed', 'deferred')
  AND dep.status_key != 'completed'
GROUP BY ri.id;

-- View: Dependency graph for visualization
CREATE VIEW IF NOT EXISTS v_dependency_graph AS
SELECT
    rd.item_id as from_id,
    ri_from.title as from_title,
    ri_from.status_key as from_status,
    rd.depends_on_id as to_id,
    ri_to.title as to_title,
    ri_to.status_key as to_status,
    rd.dependency_type
FROM roadmap_dependencies rd
JOIN roadmap_items ri_from ON ri_from.id = rd.item_id
JOIN roadmap_items ri_to ON ri_to.id = rd.depends_on_id
WHERE ri_from.deleted_at IS NULL
  AND ri_to.deleted_at IS NULL;

-- View: Items ready to start (no unmet dependencies)
CREATE VIEW IF NOT EXISTS v_ready_items AS
SELECT
    ri.id,
    ri.title,
    ri.phase_key,
    ri.owner,
    ri.rank
FROM roadmap_items ri
WHERE ri.deleted_at IS NULL
  AND ri.status_key = 'pending'
  AND ri.id NOT IN (
      SELECT rd.item_id
      FROM roadmap_dependencies rd
      JOIN roadmap_items dep ON dep.id = rd.depends_on_id
      WHERE rd.dependency_type = 'blocks'
        AND dep.status_key != 'completed'
  )
ORDER BY ri.phase_key, ri.rank;

-- =============================================================================
-- CYCLE DETECTION TRIGGER
-- =============================================================================
-- Prevents circular dependencies by checking path before insert.
-- Uses recursive CTE to detect if adding this edge creates a cycle.

CREATE TRIGGER IF NOT EXISTS roadmap_dep_no_cycles
BEFORE INSERT ON roadmap_dependencies
BEGIN
    SELECT CASE
        WHEN EXISTS (
            WITH RECURSIVE dep_chain(id, depth) AS (
                -- Start from the item we're depending on
                SELECT NEW.depends_on_id, 1
                UNION ALL
                -- Follow the dependency chain
                SELECT rd.depends_on_id, dc.depth + 1
                FROM dep_chain dc
                JOIN roadmap_dependencies rd ON rd.item_id = dc.id
                WHERE dc.depth < 100  -- Prevent infinite recursion
            )
            SELECT 1 FROM dep_chain WHERE id = NEW.item_id
        )
        THEN RAISE(ABORT, 'Circular dependency detected')
    END;
END;

-- =============================================================================
-- STATUS VALIDATION TRIGGER
-- =============================================================================
-- Prevents setting status to 'in_progress' if blocking dependencies not met.

CREATE TRIGGER IF NOT EXISTS roadmap_status_check_deps
BEFORE UPDATE OF status_key ON roadmap_items
WHEN NEW.status_key = 'in_progress' AND OLD.status_key != 'in_progress'
BEGIN
    SELECT CASE
        WHEN EXISTS (
            SELECT 1
            FROM roadmap_dependencies rd
            JOIN roadmap_items dep ON dep.id = rd.depends_on_id
            WHERE rd.item_id = NEW.id
              AND rd.dependency_type = 'blocks'
              AND dep.status_key != 'completed'
        )
        THEN RAISE(ABORT, 'Cannot start: blocking dependencies not complete')
    END;
END;

-- =============================================================================
-- AUDIT TRIGGERS
-- =============================================================================

CREATE TRIGGER IF NOT EXISTS roadmap_dep_audit_insert
AFTER INSERT ON roadmap_dependencies
BEGIN
    INSERT INTO audit_log (event_type, actor, resource_type, resource_id, action, new_value, instance_id)
    VALUES (
        'roadmap_dependency',
        COALESCE(NEW.created_by, 'system'),
        'roadmap_dependency',
        NEW.item_id || '->' || NEW.depends_on_id,
        'create',
        json_object('item_id', NEW.item_id, 'depends_on_id', NEW.depends_on_id, 'type', NEW.dependency_type),
        (SELECT value FROM instance_config WHERE key = 'instance_id')
    );
END;

CREATE TRIGGER IF NOT EXISTS roadmap_assignment_audit
AFTER INSERT ON roadmap_assignments
BEGIN
    INSERT INTO audit_log (event_type, actor, resource_type, resource_id, action, new_value, instance_id)
    VALUES (
        'roadmap_assignment',
        COALESCE(NEW.assigned_by, 'system'),
        'roadmap_assignment',
        NEW.item_id,
        'assign',
        json_object('item_id', NEW.item_id, 'agent_id', NEW.agent_id, 'role', NEW.role),
        (SELECT value FROM instance_config WHERE key = 'instance_id')
    );
END;

-- =============================================================================
-- HELPER FUNCTIONS VIA VIEWS
-- =============================================================================

-- View: Get next available rank in a phase (for appending)
CREATE VIEW IF NOT EXISTS v_next_rank AS
SELECT
    phase_key,
    COALESCE(MAX(rank), 0) + 1.0 as next_rank
FROM roadmap_items
WHERE deleted_at IS NULL
GROUP BY phase_key;

-- View: Roadmap progress with dependency info
CREATE VIEW IF NOT EXISTS v_roadmap_with_deps AS
SELECT
    ri.id,
    ri.phase_key,
    ri.title,
    ri.status_key,
    ri.owner,
    ri.rank,
    ri.target_date,
    (SELECT COUNT(*) FROM roadmap_dependencies rd WHERE rd.item_id = ri.id AND rd.dependency_type = 'blocks') as blocking_dep_count,
    (SELECT COUNT(*) FROM roadmap_dependencies rd
     JOIN roadmap_items dep ON dep.id = rd.depends_on_id
     WHERE rd.item_id = ri.id
       AND rd.dependency_type = 'blocks'
       AND dep.status_key != 'completed') as unmet_dep_count,
    (SELECT GROUP_CONCAT(agent_id, ', ') FROM roadmap_assignments ra WHERE ra.item_id = ri.id AND ra.status = 'active') as active_agents
FROM roadmap_items ri
WHERE ri.deleted_at IS NULL
ORDER BY ri.phase_key, ri.rank;

-- =============================================================================
-- DEPENDENCY CASCADE AUTOMATION
-- =============================================================================
-- These views and triggers surface the full prerequisite chain when work is
-- assigned, enabling agents to see what must complete first.

-- View: Full prerequisite chain for any item (recursive CTE)
-- Query: SELECT * FROM v_prerequisite_chain WHERE root_item_id = 'RI-005'
-- Returns: All upstream dependencies in topological order with depth
CREATE VIEW IF NOT EXISTS v_prerequisite_chain AS
WITH RECURSIVE prereq_chain(root_item_id, prereq_id, prereq_title, prereq_status, depth, path) AS (
    -- Base case: direct dependencies
    SELECT
        rd.item_id as root_item_id,
        rd.depends_on_id as prereq_id,
        ri.title as prereq_title,
        ri.status_key as prereq_status,
        1 as depth,
        rd.item_id || '->' || rd.depends_on_id as path
    FROM roadmap_dependencies rd
    JOIN roadmap_items ri ON ri.id = rd.depends_on_id
    WHERE rd.dependency_type = 'blocks'
      AND ri.deleted_at IS NULL

    UNION ALL

    -- Recursive case: dependencies of dependencies
    SELECT
        pc.root_item_id,
        rd.depends_on_id as prereq_id,
        ri.title as prereq_title,
        ri.status_key as prereq_status,
        pc.depth + 1 as depth,
        pc.path || '->' || rd.depends_on_id as path
    FROM prereq_chain pc
    JOIN roadmap_dependencies rd ON rd.item_id = pc.prereq_id
    JOIN roadmap_items ri ON ri.id = rd.depends_on_id
    WHERE rd.dependency_type = 'blocks'
      AND ri.deleted_at IS NULL
      AND pc.depth < 50  -- Prevent runaway recursion
)
SELECT DISTINCT
    root_item_id,
    prereq_id,
    prereq_title,
    prereq_status,
    depth,
    path,
    CASE WHEN prereq_status = 'completed' THEN 1 ELSE 0 END as is_complete
FROM prereq_chain
ORDER BY root_item_id, depth, prereq_id;

-- View: Assignment readiness with cascade info
-- Shows each assignment with its prerequisite status
CREATE VIEW IF NOT EXISTS v_assignment_with_prerequisites AS
SELECT
    ra.id as assignment_id,
    ra.item_id,
    ri.title as item_title,
    ra.agent_id,
    ra.role,
    ra.status as assignment_status,
    ri.status_key as item_status,
    -- Is this item ready to start?
    CASE
        WHEN ri.status_key IN ('completed', 'in_progress') THEN 'already_active'
        WHEN NOT EXISTS (
            SELECT 1 FROM roadmap_dependencies rd
            JOIN roadmap_items dep ON dep.id = rd.depends_on_id
            WHERE rd.item_id = ra.item_id
              AND rd.dependency_type = 'blocks'
              AND dep.status_key != 'completed'
        ) THEN 'ready'
        ELSE 'blocked'
    END as readiness,
    -- Count of unmet prerequisites
    (SELECT COUNT(DISTINCT prereq_id)
     FROM v_prerequisite_chain pc
     WHERE pc.root_item_id = ra.item_id
       AND pc.prereq_status != 'completed') as unmet_prereq_count,
    -- List of immediate blockers
    (SELECT GROUP_CONCAT(rd.depends_on_id, ', ')
     FROM roadmap_dependencies rd
     JOIN roadmap_items dep ON dep.id = rd.depends_on_id
     WHERE rd.item_id = ra.item_id
       AND rd.dependency_type = 'blocks'
       AND dep.status_key != 'completed') as immediate_blockers,
    -- Who is assigned to immediate blockers?
    (SELECT GROUP_CONCAT(DISTINCT ra2.agent_id, ', ')
     FROM roadmap_dependencies rd
     JOIN roadmap_items dep ON dep.id = rd.depends_on_id
     JOIN roadmap_assignments ra2 ON ra2.item_id = dep.id
     WHERE rd.item_id = ra.item_id
       AND rd.dependency_type = 'blocks'
       AND dep.status_key != 'completed'
       AND ra2.status IN ('assigned', 'active')) as blocker_assignees
FROM roadmap_assignments ra
JOIN roadmap_items ri ON ri.id = ra.item_id
WHERE ri.deleted_at IS NULL;

-- Table: Tracks unassigned prerequisites surfaced during assignment
-- When you assign X but Y is a prerequisite with no assignee, Y appears here
CREATE TABLE IF NOT EXISTS assignment_prerequisites (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_assignment_id INTEGER NOT NULL,  -- The assignment that triggered this
    prerequisite_item_id TEXT NOT NULL,     -- The item that needs assignment
    depth INTEGER NOT NULL,                 -- How many levels up in the chain
    surfaced_at TEXT NOT NULL DEFAULT (datetime('now')),
    resolved_at TEXT,                       -- When someone got assigned
    FOREIGN KEY (source_assignment_id) REFERENCES roadmap_assignments(id),
    FOREIGN KEY (prerequisite_item_id) REFERENCES roadmap_items(id)
);

CREATE INDEX IF NOT EXISTS idx_prereq_source ON assignment_prerequisites(source_assignment_id);
CREATE INDEX IF NOT EXISTS idx_prereq_unresolved ON assignment_prerequisites(prerequisite_item_id) WHERE resolved_at IS NULL;

-- Trigger: When assignment created, surface unassigned prerequisites
-- This populates assignment_prerequisites with items that need attention
CREATE TRIGGER IF NOT EXISTS roadmap_assignment_cascade
AFTER INSERT ON roadmap_assignments
BEGIN
    -- Insert all unassigned prerequisites into the cascade table
    INSERT INTO assignment_prerequisites (source_assignment_id, prerequisite_item_id, depth)
    SELECT
        NEW.id,
        pc.prereq_id,
        pc.depth
    FROM v_prerequisite_chain pc
    WHERE pc.root_item_id = NEW.item_id
      AND pc.prereq_status != 'completed'
      AND NOT EXISTS (
          SELECT 1 FROM roadmap_assignments ra
          WHERE ra.item_id = pc.prereq_id
            AND ra.status IN ('assigned', 'active')
      );

    -- Also log to audit if there are blockers
    INSERT INTO audit_log (event_type, actor, resource_type, resource_id, action, new_value, instance_id)
    SELECT
        'assignment_cascade',
        COALESCE(NEW.assigned_by, 'system'),
        'roadmap_assignment',
        NEW.item_id,
        'cascade_detected',
        json_object(
            'assignment_id', NEW.id,
            'item_id', NEW.item_id,
            'agent_id', NEW.agent_id,
            'unassigned_prereqs', (
                SELECT GROUP_CONCAT(pc.prereq_id, ', ')
                FROM v_prerequisite_chain pc
                WHERE pc.root_item_id = NEW.item_id
                  AND pc.prereq_status != 'completed'
                  AND NOT EXISTS (
                      SELECT 1 FROM roadmap_assignments ra
                      WHERE ra.item_id = pc.prereq_id
                        AND ra.status IN ('assigned', 'active')
                  )
            )
        ),
        (SELECT value FROM instance_config WHERE key = 'instance_id')
    WHERE EXISTS (
        SELECT 1 FROM v_prerequisite_chain pc
        WHERE pc.root_item_id = NEW.item_id
          AND pc.prereq_status != 'completed'
          AND NOT EXISTS (
              SELECT 1 FROM roadmap_assignments ra
              WHERE ra.item_id = pc.prereq_id
                AND ra.status IN ('assigned', 'active')
          )
    );
END;

-- Trigger: When prerequisite gets assigned, mark cascade entry resolved
CREATE TRIGGER IF NOT EXISTS roadmap_prereq_resolved
AFTER INSERT ON roadmap_assignments
BEGIN
    UPDATE assignment_prerequisites
    SET resolved_at = datetime('now')
    WHERE prerequisite_item_id = NEW.item_id
      AND resolved_at IS NULL;
END;

-- View: Unassigned prerequisites needing attention
-- Agents should check this view to see what cascade work needs assignment
CREATE VIEW IF NOT EXISTS v_unassigned_prerequisites AS
SELECT
    ap.prerequisite_item_id,
    ri.title as prereq_title,
    ri.phase_key,
    ri.status_key,
    COUNT(DISTINCT ap.source_assignment_id) as blocking_count,
    GROUP_CONCAT(ri_source.title, ', ') as blocks_items,
    MIN(ap.depth) as min_depth  -- Closest to a leaf
FROM assignment_prerequisites ap
JOIN roadmap_items ri ON ri.id = ap.prerequisite_item_id
JOIN roadmap_assignments ra ON ra.id = ap.source_assignment_id
JOIN roadmap_items ri_source ON ri_source.id = ra.item_id
WHERE ap.resolved_at IS NULL
  AND ri.deleted_at IS NULL
  AND ri.status_key != 'completed'
GROUP BY ap.prerequisite_item_id
ORDER BY blocking_count DESC, min_depth ASC;

-- DOWN

-- Drop cascade automation first (depends on other objects)
DROP VIEW IF EXISTS v_unassigned_prerequisites;
DROP TRIGGER IF EXISTS roadmap_prereq_resolved;
DROP TRIGGER IF EXISTS roadmap_assignment_cascade;
DROP INDEX IF EXISTS idx_prereq_unresolved;
DROP INDEX IF EXISTS idx_prereq_source;
DROP TABLE IF EXISTS assignment_prerequisites;
DROP VIEW IF EXISTS v_assignment_with_prerequisites;
DROP VIEW IF EXISTS v_prerequisite_chain;

-- Drop base views
DROP VIEW IF EXISTS v_roadmap_with_deps;
DROP VIEW IF EXISTS v_next_rank;
DROP VIEW IF EXISTS v_ready_items;
DROP VIEW IF EXISTS v_dependency_graph;
DROP VIEW IF EXISTS v_blocked_items;

-- Drop triggers
DROP TRIGGER IF EXISTS roadmap_assignment_audit;
DROP TRIGGER IF EXISTS roadmap_dep_audit_insert;
DROP TRIGGER IF EXISTS roadmap_status_check_deps;
DROP TRIGGER IF EXISTS roadmap_dep_no_cycles;

-- Drop indexes
DROP INDEX IF EXISTS idx_roadmap_rank;
DROP INDEX IF EXISTS idx_assignment_status;
DROP INDEX IF EXISTS idx_assignment_agent;
DROP INDEX IF EXISTS idx_assignment_item;
DROP INDEX IF EXISTS idx_roadmap_dep_depends;
DROP INDEX IF EXISTS idx_roadmap_dep_item;

-- Drop tables
DROP TABLE IF EXISTS roadmap_assignments;
DROP TABLE IF EXISTS roadmap_dependencies;

-- Note: Cannot easily drop column in SQLite, leave rank column
