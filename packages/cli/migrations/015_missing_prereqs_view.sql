-- Migration 015: Create v_missing_prereqs view
-- Purpose: Surface missing prerequisites for roadmap items
-- Types: approval_required, blocker_unresolved, dependency_incomplete

-- UP

-- Drop existing view if exists (for re-runs)
DROP VIEW IF EXISTS v_missing_prereqs;

-- Create the missing prerequisites view
CREATE VIEW v_missing_prereqs AS
-- Type 1: Approval required (depends on incomplete gate)
SELECT
    rd.item_id,
    'approval_required' as prereq_type,
    rd.depends_on_id as prereq_id,
    dep.status_key as prereq_status,
    dep.title as prereq_title,
    dep.item_type as prereq_item_type
FROM roadmap_dependencies rd
JOIN roadmap_items dep ON dep.id = rd.depends_on_id
JOIN roadmap_items ri ON ri.id = rd.item_id
WHERE dep.item_type = 'gate'
  AND dep.status_key NOT IN ('completed')
  AND dep.deleted_at IS NULL
  AND ri.deleted_at IS NULL
  AND ri.status_key NOT IN ('completed', 'deferred')

UNION ALL

-- Type 2: Blocker unresolved (blocking dependency not completed)
SELECT
    rd.item_id,
    'blocker_unresolved' as prereq_type,
    rd.depends_on_id as prereq_id,
    dep.status_key as prereq_status,
    dep.title as prereq_title,
    dep.item_type as prereq_item_type
FROM roadmap_dependencies rd
JOIN roadmap_items dep ON dep.id = rd.depends_on_id
JOIN roadmap_items ri ON ri.id = rd.item_id
WHERE rd.dependency_type = 'blocks'
  AND dep.item_type != 'gate'  -- Gates handled above
  AND dep.status_key NOT IN ('completed')
  AND dep.deleted_at IS NULL
  AND ri.deleted_at IS NULL
  AND ri.status_key NOT IN ('completed', 'deferred')

UNION ALL

-- Type 3: Dependency incomplete (soft dependency not completed)
SELECT
    rd.item_id,
    'dependency_incomplete' as prereq_type,
    rd.depends_on_id as prereq_id,
    dep.status_key as prereq_status,
    dep.title as prereq_title,
    dep.item_type as prereq_item_type
FROM roadmap_dependencies rd
JOIN roadmap_items dep ON dep.id = rd.depends_on_id
JOIN roadmap_items ri ON ri.id = rd.item_id
WHERE rd.dependency_type = 'soft'
  AND dep.status_key NOT IN ('completed')
  AND dep.deleted_at IS NULL
  AND ri.deleted_at IS NULL
  AND ri.status_key NOT IN ('completed', 'deferred')
;

-- Add index for performance (if not exists)
-- Note: Indexes on views are not supported in SQLite, but the base tables
-- already have appropriate indexes via idx_roadmap_dep_item and idx_roadmap_dep_depends
