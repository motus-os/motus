-- Migration: 005_program_management
-- Version: 5
-- Description: Program management (products, features, CRs, roadmap, bugs)
-- Reference: Stripe API versioning, Spotify Backstage catalog
--
-- =============================================================================
-- DESIGN DECISION: ON DELETE Strategy
-- =============================================================================
-- CHOICE: No ON DELETE clauses (SQLite default = RESTRICT)
--
-- RATIONALE:
-- 1. Soft deletes are the primary deletion mechanism (deleted_at column)
-- 2. RESTRICT prevents accidental orphans - you can't hard-delete a parent
--    if children reference it
-- 3. CASCADE would be dangerous - deleting a program would cascade to
--    products, features, CRs, losing all history
-- 4. SET NULL would break referential integrity and lose relationships
--
-- WORKFLOW:
-- - Soft delete: Set deleted_at = datetime('now') on the record
-- - Child records stay intact (historical reference preserved)
-- - Views filter deleted_at IS NULL for active queries
-- - Hard delete: Only for data correction, must delete children first
--
-- This matches Stripe's pattern where subscription objects remain in the
-- API after cancellation, preserving audit trail and history.
-- =============================================================================

-- UP

-- =============================================================================
-- TERMINOLOGY EXTENSIONS (stable keys, changeable display names)
-- =============================================================================

-- Product lifecycle states
INSERT INTO terminology (domain, internal_key, display_name, description, sort_order) VALUES
('product_status', 'active', 'Active', 'Product is actively developed', 1),
('product_status', 'maintenance', 'Maintenance', 'Bug fixes only', 2),
('product_status', 'deprecated', 'Deprecated', 'No new development', 3),
('product_status', 'archived', 'Archived', 'No longer supported', 4);

-- Feature lifecycle states
INSERT INTO terminology (domain, internal_key, display_name, description, sort_order) VALUES
('feature_status', 'planned', 'Planned', 'Not yet started', 1),
('feature_status', 'in_development', 'In Development', 'Active work', 2),
('feature_status', 'beta', 'Beta', 'Testing phase', 3),
('feature_status', 'stable', 'Stable', 'Production ready', 4),
('feature_status', 'deprecated', 'Deprecated', 'Being phased out', 5);

-- Roadmap phases
INSERT INTO terminology (domain, internal_key, display_name, description, sort_order) VALUES
('roadmap_phase', 'phase_a', 'Phase A', 'Foundation', 1),
('roadmap_phase', 'phase_b', 'Phase B', 'Core Development', 2),
('roadmap_phase', 'phase_c', 'Phase C', 'Functional Verification', 3),
('roadmap_phase', 'phase_d', 'Phase D', 'Claims Validation', 4),
('roadmap_phase', 'phase_e', 'Phase E', 'Release Preparation', 5),
('roadmap_phase', 'post_launch', 'Post-Launch', 'Maintenance and growth', 6);

-- Roadmap item status
INSERT INTO terminology (domain, internal_key, display_name, description, sort_order) VALUES
('roadmap_status', 'pending', 'Pending', 'Not started', 1),
('roadmap_status', 'in_progress', 'In Progress', 'Active work', 2),
('roadmap_status', 'blocked', 'Blocked', 'Waiting on dependency', 3),
('roadmap_status', 'completed', 'Completed', 'Done', 4),
('roadmap_status', 'deferred', 'Deferred', 'Moved to later phase', 5);

-- Bug severity
INSERT INTO terminology (domain, internal_key, display_name, description, sort_order) VALUES
('bug_severity', 'critical', 'Critical', 'System unusable', 1),
('bug_severity', 'high', 'High', 'Major feature broken', 2),
('bug_severity', 'medium', 'Medium', 'Feature degraded', 3),
('bug_severity', 'low', 'Low', 'Minor issue', 4);

-- Bug status
INSERT INTO terminology (domain, internal_key, display_name, description, sort_order) VALUES
('bug_status', 'open', 'Open', 'Not yet addressed', 1),
('bug_status', 'confirmed', 'Confirmed', 'Reproduced', 2),
('bug_status', 'in_progress', 'In Progress', 'Being fixed', 3),
('bug_status', 'fixed', 'Fixed', 'Fix implemented', 4),
('bug_status', 'verified', 'Verified', 'Fix confirmed', 5),
('bug_status', 'wont_fix', 'Won''t Fix', 'Intentional or not worth fixing', 6);

-- Charter document types (singletons per program)
INSERT INTO terminology (domain, internal_key, display_name, description, sort_order) VALUES
('charter_type', 'roadmap', 'Roadmap', 'Single source of truth for planning', 1),
('charter_type', 'ethos', 'Ethos', 'Agent operating principles', 2),
('charter_type', 'release_checklist', 'Release Checklist', 'Go-live verification', 3);

-- Program types (software, content, infrastructure)
INSERT INTO terminology (domain, internal_key, display_name, description, sort_order) VALUES
('program_type', 'software', 'Software', 'Code-based deliverables', 1),
('program_type', 'content', 'Content', 'Written/media deliverables', 2),
('program_type', 'infrastructure', 'Infrastructure', 'Systems and tooling', 3);

-- Release types
INSERT INTO terminology (domain, internal_key, display_name, description, sort_order) VALUES
('release_type', 'version', 'Version', 'Semantic versioned software release', 1),
('release_type', 'post', 'Post', 'Blog post or article', 2),
('release_type', 'campaign', 'Campaign', 'Marketing or outreach campaign', 3),
('release_type', 'deploy', 'Deploy', 'Infrastructure deployment', 4);

-- Release statuses
INSERT INTO terminology (domain, internal_key, display_name, description, sort_order) VALUES
('release_status', 'pending', 'Pending', 'Not yet started', 1),
('release_status', 'in_progress', 'In Progress', 'Active work', 2),
('release_status', 'ready', 'Ready', 'Ready for release', 3),
('release_status', 'published', 'Published', 'Released to public', 4),
('release_status', 'archived', 'Archived', 'No longer active', 5);

-- Standard levels (where standards apply)
INSERT INTO terminology (domain, internal_key, display_name, description, sort_order) VALUES
('standard_level', 'program', 'Program', 'Standards for entire program', 1),
('standard_level', 'product', 'Product', 'Standards for product', 2),
('standard_level', 'feature', 'Feature', 'Standards for feature', 3),
('standard_level', 'release', 'Release', 'Standards for release', 4),
('standard_level', 'cr', 'CR', 'Standards for change request', 5);

-- Standard check types
INSERT INTO terminology (domain, internal_key, display_name, description, sort_order) VALUES
('check_type', 'boolean', 'Boolean', 'Pass/Fail check', 1),
('check_type', 'threshold', 'Threshold', 'Numeric threshold check', 2),
('check_type', 'pattern', 'Pattern', 'Regex pattern check', 3),
('check_type', 'manual', 'Manual', 'Human verification required', 4);

-- =============================================================================
-- PROGRAMS (top-level containers - software, content, infrastructure)
-- =============================================================================

CREATE TABLE programs (
    id TEXT PRIMARY KEY,                    -- 'motus-cli', 'bens-linkedin', 'example-infra'
    name TEXT NOT NULL,
    description TEXT,
    type_key TEXT NOT NULL DEFAULT 'software',
    status_key TEXT NOT NULL DEFAULT 'active',
    owner TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    deleted_at TEXT
    -- NOTE: type_key and status_key reference terminology.internal_key
    -- but terminology.internal_key is not unique (domain-scoped).
    -- Validation is application-level via terminology table lookups.
);

CREATE INDEX idx_programs_type ON programs(type_key) WHERE deleted_at IS NULL;
CREATE INDEX idx_programs_active ON programs(id) WHERE deleted_at IS NULL;

-- =============================================================================
-- PRODUCTS (top-level entities within programs)
-- =============================================================================

CREATE TABLE products (
    id TEXT PRIMARY KEY,                    -- 'motus', 'motus-web', 'motus-crypto'
    program_id TEXT NOT NULL,               -- Parent program
    name TEXT NOT NULL,                     -- Display name (can change)
    description TEXT,
    status_key TEXT NOT NULL DEFAULT 'active',
    version TEXT NOT NULL DEFAULT '0.0.0',  -- Current version
    repository_url TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    deleted_at TEXT,                        -- Soft delete

    FOREIGN KEY (program_id) REFERENCES programs(id)
    -- status_key validated via terminology lookup (not FK - see design note)
);

CREATE INDEX idx_products_program ON products(program_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_products_status ON products(status_key) WHERE deleted_at IS NULL;
CREATE INDEX idx_products_active ON products(id) WHERE deleted_at IS NULL;

-- =============================================================================
-- FEATURES (capabilities within products)
-- =============================================================================

CREATE TABLE features (
    id TEXT PRIMARY KEY,                    -- 'coordination-api', 'policy-gates'
    product_id TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    status_key TEXT NOT NULL DEFAULT 'planned',
    version TEXT,                           -- Feature-specific version
    introduced_in TEXT,                     -- Product version when added
    deprecated_in TEXT,                     -- Product version when deprecated
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    deleted_at TEXT,

    FOREIGN KEY (product_id) REFERENCES products(id)
);

CREATE INDEX idx_features_product ON features(product_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_features_status ON features(status_key) WHERE deleted_at IS NULL;
CREATE INDEX idx_features_version ON features(product_id, version) WHERE deleted_at IS NULL;

-- =============================================================================
-- CHANGE REQUESTS (work items)
-- =============================================================================

CREATE TABLE change_requests (
    id TEXT PRIMARY KEY,                    -- 'CR-2025-12-26-001'
    title TEXT NOT NULL,
    description TEXT,
    status_key TEXT NOT NULL DEFAULT 'queue',
    type_key TEXT NOT NULL DEFAULT 'enhancement',
    size TEXT NOT NULL DEFAULT 'M' CHECK (size IN ('S', 'M', 'L', 'XL')),
    owner TEXT,                             -- Agent or person ID
    product_id TEXT,
    feature_id TEXT,
    target_version TEXT,                    -- Version this CR targets
    completed_version TEXT,                 -- Version this CR shipped in
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    started_at TEXT,
    completed_at TEXT,
    deleted_at TEXT,

    FOREIGN KEY (product_id) REFERENCES products(id),
    FOREIGN KEY (feature_id) REFERENCES features(id)
    -- status_key, type_key validated via terminology lookup (not FK - see design note)
);

CREATE INDEX idx_cr_status ON change_requests(status_key) WHERE deleted_at IS NULL;
CREATE INDEX idx_cr_product ON change_requests(product_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_cr_feature ON change_requests(feature_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_cr_owner ON change_requests(owner) WHERE deleted_at IS NULL;
CREATE INDEX idx_cr_target ON change_requests(target_version) WHERE deleted_at IS NULL;

-- =============================================================================
-- CR DEPENDENCIES (directed graph)
-- =============================================================================

CREATE TABLE cr_dependencies (
    cr_id TEXT NOT NULL,
    depends_on_id TEXT NOT NULL,
    dependency_type TEXT NOT NULL DEFAULT 'blocks'
        CHECK (dependency_type IN ('blocks', 'related', 'supersedes')),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),

    PRIMARY KEY (cr_id, depends_on_id),
    FOREIGN KEY (cr_id) REFERENCES change_requests(id),
    FOREIGN KEY (depends_on_id) REFERENCES change_requests(id),
    CHECK (cr_id != depends_on_id)
);

CREATE INDEX idx_cr_dep_blocks ON cr_dependencies(depends_on_id);

-- =============================================================================
-- ROADMAP ITEMS (phase-based planning)
-- =============================================================================

CREATE TABLE roadmap_items (
    id TEXT PRIMARY KEY,                    -- 'RI-001'
    phase_key TEXT NOT NULL,                -- References terminology
    title TEXT NOT NULL,
    description TEXT,
    status_key TEXT NOT NULL DEFAULT 'pending',
    owner TEXT,
    scope TEXT NOT NULL DEFAULT 'user',
    feature_id TEXT,
    cr_id TEXT,                             -- Optional link to CR
    target_date TEXT,
    completed_at TEXT,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_by TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    deleted_at TEXT,

    -- phase_key validated via terminology lookup (not FK - see design note)
    -- status_key validated via terminology lookup (not FK - see design note),
    FOREIGN KEY (feature_id) REFERENCES features(id),
    FOREIGN KEY (cr_id) REFERENCES change_requests(id)
);

CREATE INDEX idx_roadmap_phase ON roadmap_items(phase_key) WHERE deleted_at IS NULL;
CREATE INDEX idx_roadmap_status ON roadmap_items(status_key) WHERE deleted_at IS NULL;
CREATE INDEX idx_roadmap_sort ON roadmap_items(phase_key, sort_order) WHERE deleted_at IS NULL;

-- =============================================================================
-- BUGS (version-specific defects)
-- =============================================================================

CREATE TABLE bugs (
    id TEXT PRIMARY KEY,                    -- 'BUG-2025-12-26-001'
    title TEXT NOT NULL,
    description TEXT,
    feature_id TEXT NOT NULL,
    feature_version TEXT NOT NULL,          -- 'context v0.1.1'
    severity_key TEXT NOT NULL DEFAULT 'medium',
    status_key TEXT NOT NULL DEFAULT 'open',
    reported_by TEXT,
    assigned_to TEXT,
    fix_cr_id TEXT,                         -- CR that fixes this bug
    fixed_in_version TEXT,                  -- Version containing fix
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    resolved_at TEXT,
    deleted_at TEXT,

    FOREIGN KEY (feature_id) REFERENCES features(id),
    -- severity_key validated via terminology lookup (not FK - see design note)
    -- status_key validated via terminology lookup (not FK - see design note),
    FOREIGN KEY (fix_cr_id) REFERENCES change_requests(id)
);

CREATE INDEX idx_bugs_feature ON bugs(feature_id, feature_version) WHERE deleted_at IS NULL;
CREATE INDEX idx_bugs_status ON bugs(status_key) WHERE deleted_at IS NULL;
CREATE INDEX idx_bugs_severity ON bugs(severity_key) WHERE deleted_at IS NULL;
CREATE INDEX idx_bugs_fix ON bugs(fix_cr_id) WHERE deleted_at IS NULL;

-- =============================================================================
-- RELEASES (generalized: versions, posts, campaigns)
-- =============================================================================

CREATE TABLE releases (
    id TEXT PRIMARY KEY,                    -- 'v0.1.0', 'post-2025-12-26-001'
    product_id TEXT NOT NULL,
    type_key TEXT NOT NULL DEFAULT 'version',
    name TEXT NOT NULL,                     -- 'v0.1.0', 'Know Don't Guess Launch Post'
    description TEXT,
    status_key TEXT NOT NULL DEFAULT 'pending',
    target_date TEXT,
    published_at TEXT,
    external_url TEXT,                      -- PyPI, LinkedIn, etc.
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    deleted_at TEXT,

    FOREIGN KEY (product_id) REFERENCES products(id)
    -- type_key, status_key validated via terminology lookup (not FK - see design note)
);

CREATE INDEX idx_releases_product ON releases(product_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_releases_type ON releases(type_key) WHERE deleted_at IS NULL;
CREATE INDEX idx_releases_status ON releases(status_key) WHERE deleted_at IS NULL;

-- =============================================================================
-- STANDARDS (quality gates at every level - the Motus difference)
-- =============================================================================

CREATE TABLE standards (
    id TEXT PRIMARY KEY,                    -- 'STD-001'
    name TEXT NOT NULL,                     -- 'No blocklist terms'
    description TEXT,
    level_key TEXT NOT NULL,                -- 'program', 'product', 'feature', 'release', 'cr'
    check_type_key TEXT NOT NULL,           -- 'boolean', 'threshold', 'pattern', 'manual'
    check_command TEXT,                     -- Bash command for boolean/pattern
    check_pattern TEXT,                     -- Regex for pattern check
    threshold_min REAL,                     -- For threshold checks
    threshold_max REAL,
    failure_message TEXT NOT NULL,
    is_blocking INTEGER NOT NULL DEFAULT 1, -- Blocks release if fails
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    deleted_at TEXT
    -- level_key, check_type_key validated via terminology lookup (not FK - see design note)
);

CREATE INDEX idx_standards_level ON standards(level_key) WHERE deleted_at IS NULL;
CREATE INDEX idx_standards_blocking ON standards(is_blocking) WHERE deleted_at IS NULL;

-- =============================================================================
-- STANDARD ASSIGNMENTS (which standards apply to which entities)
-- =============================================================================

CREATE TABLE standard_assignments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    standard_id TEXT NOT NULL,
    entity_type TEXT NOT NULL,              -- 'program', 'product', 'feature', 'release'
    entity_id TEXT NOT NULL,
    inherited INTEGER NOT NULL DEFAULT 0,   -- Inherited from parent
    created_at TEXT NOT NULL DEFAULT (datetime('now')),

    FOREIGN KEY (standard_id) REFERENCES standards(id),
    UNIQUE(standard_id, entity_type, entity_id)
);

CREATE INDEX idx_assignments_entity ON standard_assignments(entity_type, entity_id);
CREATE INDEX idx_assignments_standard ON standard_assignments(standard_id);

-- =============================================================================
-- COMPLIANCE RESULTS (audit trail of standard checks)
-- =============================================================================

CREATE TABLE compliance_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    standard_id TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    release_id TEXT,                        -- Which release was this for
    result TEXT NOT NULL CHECK (result IN ('pass', 'fail', 'skip', 'error')),
    result_value TEXT,                      -- Actual value for threshold checks
    error_message TEXT,
    checked_by TEXT NOT NULL,               -- 'agent:builder-1', 'system', 'user:ben'
    checked_at TEXT NOT NULL DEFAULT (datetime('now')),

    FOREIGN KEY (standard_id) REFERENCES standards(id),
    FOREIGN KEY (release_id) REFERENCES releases(id)
);

-- Immutable audit trail
CREATE TRIGGER compliance_immutable
BEFORE UPDATE ON compliance_results
BEGIN
    SELECT RAISE(ABORT, 'Compliance results are immutable');
END;

CREATE TRIGGER compliance_no_delete
BEFORE DELETE ON compliance_results
BEGIN
    SELECT RAISE(ABORT, 'Compliance results cannot be deleted');
END;

CREATE INDEX idx_compliance_entity ON compliance_results(entity_type, entity_id);
CREATE INDEX idx_compliance_release ON compliance_results(release_id);
CREATE INDEX idx_compliance_result ON compliance_results(result);
CREATE INDEX idx_compliance_standard ON compliance_results(standard_id);

-- =============================================================================
-- CHARTER DOCUMENTS (singletons per program - ONE roadmap, ONE ethos)
-- =============================================================================

CREATE TABLE charter_docs (
    id TEXT PRIMARY KEY,                    -- 'charter-roadmap-v2.1'
    doc_type_key TEXT NOT NULL,             -- 'roadmap', 'ethos', 'release_checklist'
    version TEXT NOT NULL,                  -- '2.1'
    title TEXT NOT NULL,
    content_hash TEXT NOT NULL,             -- SHA-256 of content
    file_path TEXT,                         -- Path to .md file if exists
    is_active INTEGER NOT NULL DEFAULT 1,   -- Only ONE active per type
    approved_by TEXT,
    approved_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    deleted_at TEXT
    -- doc_type_key validated via terminology lookup (not FK - see design note)
);

-- CRITICAL: Enforce singleton - only ONE active document per type
CREATE UNIQUE INDEX idx_charter_singleton
ON charter_docs(doc_type_key)
WHERE is_active = 1 AND deleted_at IS NULL;

CREATE INDEX idx_charter_type ON charter_docs(doc_type_key) WHERE deleted_at IS NULL;
CREATE INDEX idx_charter_version ON charter_docs(doc_type_key, version);

-- Trigger: Deactivate old when new becomes active
CREATE TRIGGER charter_singleton_enforce
BEFORE INSERT ON charter_docs
WHEN NEW.is_active = 1
BEGIN
    UPDATE charter_docs
    SET is_active = 0, updated_at = datetime('now')
    WHERE doc_type_key = NEW.doc_type_key
    AND is_active = 1
    AND deleted_at IS NULL;
END;

-- =============================================================================
-- VERSION HISTORY (entity snapshots - Stripe pattern)
-- =============================================================================

CREATE TABLE entity_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_type TEXT NOT NULL,              -- 'product', 'feature', 'cr', 'bug'
    entity_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    data TEXT NOT NULL,                     -- JSON snapshot
    changed_by TEXT NOT NULL,
    change_reason TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),

    UNIQUE(entity_type, entity_id, version)
);

CREATE INDEX idx_versions_entity ON entity_versions(entity_type, entity_id);
CREATE INDEX idx_versions_latest ON entity_versions(entity_type, entity_id, version DESC);

-- Immutability triggers for entity_versions (audit trail protection)
CREATE TRIGGER entity_versions_immutable
BEFORE UPDATE ON entity_versions
BEGIN
    SELECT RAISE(ABORT, 'Entity version history is immutable');
END;

CREATE TRIGGER entity_versions_no_delete
BEFORE DELETE ON entity_versions
BEGIN
    SELECT RAISE(ABORT, 'Entity version history cannot be deleted');
END;

-- Trigger: Auto-capture version on CR update
CREATE TRIGGER cr_version_capture
AFTER UPDATE ON change_requests
WHEN OLD.updated_at != NEW.updated_at
BEGIN
    INSERT INTO entity_versions (entity_type, entity_id, version, data, changed_by)
    SELECT
        'cr',
        NEW.id,
        COALESCE((SELECT MAX(version) FROM entity_versions
                  WHERE entity_type = 'cr' AND entity_id = NEW.id), 0) + 1,
        json_object(
            'title', NEW.title,
            'status_key', NEW.status_key,
            'type_key', NEW.type_key,
            'size', NEW.size,
            'owner', NEW.owner,
            'product_id', NEW.product_id,
            'feature_id', NEW.feature_id,
            'target_version', NEW.target_version
        ),
        COALESCE(NEW.owner, 'system');
END;

-- Trigger: Auto-capture version on product update
CREATE TRIGGER product_version_capture
AFTER UPDATE ON products
WHEN OLD.updated_at != NEW.updated_at
BEGIN
    INSERT INTO entity_versions (entity_type, entity_id, version, data, changed_by)
    SELECT
        'product',
        NEW.id,
        COALESCE((SELECT MAX(version) FROM entity_versions
                  WHERE entity_type = 'product' AND entity_id = NEW.id), 0) + 1,
        json_object(
            'name', NEW.name,
            'status_key', NEW.status_key,
            'version', NEW.version,
            'program_id', NEW.program_id
        ),
        'system';
END;

-- Trigger: Auto-capture version on feature update
CREATE TRIGGER feature_version_capture
AFTER UPDATE ON features
WHEN OLD.updated_at != NEW.updated_at
BEGIN
    INSERT INTO entity_versions (entity_type, entity_id, version, data, changed_by)
    SELECT
        'feature',
        NEW.id,
        COALESCE((SELECT MAX(version) FROM entity_versions
                  WHERE entity_type = 'feature' AND entity_id = NEW.id), 0) + 1,
        json_object(
            'name', NEW.name,
            'status_key', NEW.status_key,
            'version', NEW.version,
            'product_id', NEW.product_id
        ),
        'system';
END;

-- Trigger: Auto-capture version on bug update
CREATE TRIGGER bug_version_capture
AFTER UPDATE ON bugs
WHEN OLD.updated_at != NEW.updated_at
BEGIN
    INSERT INTO entity_versions (entity_type, entity_id, version, data, changed_by)
    SELECT
        'bug',
        NEW.id,
        COALESCE((SELECT MAX(version) FROM entity_versions
                  WHERE entity_type = 'bug' AND entity_id = NEW.id), 0) + 1,
        json_object(
            'title', NEW.title,
            'status_key', NEW.status_key,
            'severity_key', NEW.severity_key,
            'feature_id', NEW.feature_id,
            'feature_version', NEW.feature_version,
            'fix_cr_id', NEW.fix_cr_id
        ),
        COALESCE(NEW.assigned_to, 'system');
END;

-- Trigger: Auto-capture version on roadmap item update
CREATE TRIGGER roadmap_version_capture
AFTER UPDATE ON roadmap_items
WHEN OLD.updated_at != NEW.updated_at
BEGIN
    INSERT INTO entity_versions (entity_type, entity_id, version, data, changed_by)
    SELECT
        'roadmap_item',
        NEW.id,
        COALESCE((SELECT MAX(version) FROM entity_versions
                  WHERE entity_type = 'roadmap_item' AND entity_id = NEW.id), 0) + 1,
        json_object(
            'title', NEW.title,
            'phase_key', NEW.phase_key,
            'status_key', NEW.status_key,
            'owner', NEW.owner,
            'target_date', NEW.target_date
        ),
        COALESCE(NEW.owner, 'system');
END;

-- =============================================================================
-- VIEWS (common queries)
-- =============================================================================

-- Open CRs by product
CREATE VIEW v_open_crs AS
SELECT
    cr.id,
    cr.title,
    cr.status_key,
    t_status.display_name as status,
    cr.size,
    cr.owner,
    p.name as product_name,
    f.name as feature_name,
    cr.target_version,
    cr.created_at
FROM change_requests cr
LEFT JOIN products p ON cr.product_id = p.id
LEFT JOIN features f ON cr.feature_id = f.id
LEFT JOIN terminology t_status ON t_status.domain = 'cr_status' AND t_status.internal_key = cr.status_key
WHERE cr.status_key NOT IN ('done')
AND cr.deleted_at IS NULL
ORDER BY cr.created_at DESC;

-- Bugs by feature version
CREATE VIEW v_bugs_by_version AS
SELECT
    b.id,
    b.title,
    f.name as feature_name,
    b.feature_version,
    t_sev.display_name as severity,
    t_stat.display_name as status,
    b.fix_cr_id,
    b.fixed_in_version,
    b.created_at
FROM bugs b
JOIN features f ON b.feature_id = f.id
LEFT JOIN terminology t_sev ON t_sev.domain = 'bug_severity' AND t_sev.internal_key = b.severity_key
LEFT JOIN terminology t_stat ON t_stat.domain = 'bug_status' AND t_stat.internal_key = b.status_key
WHERE b.deleted_at IS NULL
ORDER BY
    CASE b.severity_key WHEN 'critical' THEN 1 WHEN 'high' THEN 2 WHEN 'medium' THEN 3 ELSE 4 END,
    b.created_at DESC;

-- Roadmap progress by phase
CREATE VIEW v_roadmap_progress AS
SELECT
    r.phase_key,
    t_phase.display_name as phase,
    COUNT(*) as total_items,
    SUM(CASE WHEN r.status_key = 'completed' THEN 1 ELSE 0 END) as completed,
    SUM(CASE WHEN r.status_key = 'in_progress' THEN 1 ELSE 0 END) as in_progress,
    SUM(CASE WHEN r.status_key = 'blocked' THEN 1 ELSE 0 END) as blocked,
    ROUND(100.0 * SUM(CASE WHEN r.status_key = 'completed' THEN 1 ELSE 0 END) / COUNT(*), 1) as pct_complete
FROM roadmap_items r
LEFT JOIN terminology t_phase ON t_phase.domain = 'roadmap_phase' AND t_phase.internal_key = r.phase_key
WHERE r.deleted_at IS NULL
GROUP BY r.phase_key, t_phase.display_name
ORDER BY t_phase.sort_order;

-- Active charter documents
CREATE VIEW v_active_charters AS
SELECT
    c.id,
    c.doc_type_key,
    t.display_name as doc_type,
    c.version,
    c.title,
    c.approved_by,
    c.approved_at,
    c.created_at
FROM charter_docs c
LEFT JOIN terminology t ON t.domain = 'charter_type' AND t.internal_key = c.doc_type_key
WHERE c.is_active = 1 AND c.deleted_at IS NULL;

-- Compliance status by release
CREATE VIEW v_compliance_status AS
SELECT
    r.id as release_id,
    r.name as release_name,
    p.name as product_name,
    COUNT(DISTINCT cr.standard_id) as total_checks,
    SUM(CASE WHEN cr.result = 'pass' THEN 1 ELSE 0 END) as passed,
    SUM(CASE WHEN cr.result = 'fail' THEN 1 ELSE 0 END) as failed,
    CASE
        WHEN SUM(CASE WHEN cr.result = 'fail' AND s.is_blocking = 1 THEN 1 ELSE 0 END) > 0 THEN 'blocked'
        WHEN SUM(CASE WHEN cr.result = 'fail' THEN 1 ELSE 0 END) > 0 THEN 'warnings'
        ELSE 'clear'
    END as status
FROM releases r
JOIN products p ON r.product_id = p.id
LEFT JOIN compliance_results cr ON cr.release_id = r.id
LEFT JOIN standards s ON cr.standard_id = s.id
WHERE r.deleted_at IS NULL
GROUP BY r.id, r.name, p.name;

-- Standards by level with assignment count
CREATE VIEW v_standards_summary AS
SELECT
    s.id,
    s.name,
    t_level.display_name as level,
    t_check.display_name as check_type,
    s.is_blocking,
    COUNT(sa.id) as assignments,
    s.created_at
FROM standards s
LEFT JOIN terminology t_level ON t_level.domain = 'standard_level' AND t_level.internal_key = s.level_key
LEFT JOIN terminology t_check ON t_check.domain = 'check_type' AND t_check.internal_key = s.check_type_key
LEFT JOIN standard_assignments sa ON sa.standard_id = s.id
WHERE s.deleted_at IS NULL
GROUP BY s.id, s.name, t_level.display_name, t_check.display_name, s.is_blocking, s.created_at
ORDER BY t_level.sort_order, s.sort_order;

-- Programs with product counts
CREATE VIEW v_programs_summary AS
SELECT
    pr.id,
    pr.name,
    t_type.display_name as type,
    t_status.display_name as status,
    pr.owner,
    COUNT(p.id) as product_count,
    pr.created_at
FROM programs pr
LEFT JOIN terminology t_type ON t_type.domain = 'program_type' AND t_type.internal_key = pr.type_key
LEFT JOIN terminology t_status ON t_status.domain = 'product_status' AND t_status.internal_key = pr.status_key
LEFT JOIN products p ON p.program_id = pr.id AND p.deleted_at IS NULL
WHERE pr.deleted_at IS NULL
GROUP BY pr.id, pr.name, t_type.display_name, t_status.display_name, pr.owner, pr.created_at;

-- =============================================================================
-- SEED DATA
-- =============================================================================

-- Programs (top-level containers)
INSERT INTO programs (id, name, description, type_key, owner) VALUES
('motus-cli', 'Motus CLI', 'Multi-agent coordination framework', 'software', 'cli-agent'),
('bens-linkedin', 'Ben''s LinkedIn', 'Thought leadership content', 'content', 'content-agent'),
('example-infra', 'Example Infrastructure', 'Systems and tooling', 'infrastructure', 'infra-agent');

-- Products within programs
INSERT INTO products (id, program_id, name, description, version) VALUES
('motus', 'motus-cli', 'Motus', 'Multi-agent coordination framework', '0.4.5'),
('motus-web', 'motus-cli', 'Motus Web', 'Dashboard and visualization', '0.1.0'),
('linkedin-posts', 'bens-linkedin', 'LinkedIn Posts', 'Thought leadership posts', '1.0.0');

-- Features within products
INSERT INTO features (id, product_id, name, description, status_key, version) VALUES
('coordination-api', 'motus', 'Coordination API', '6-call API (peek, claim, release, heartbeat, force_release, get_state)', 'stable', '0.1.0'),
('policy-gates', 'motus', 'Policy Gates', 'HMAC-signed permits for action verification', 'stable', '0.1.0'),
('session-sync', 'motus', 'Session Sync', 'Claude/Codex/Gemini transcript parsing', 'stable', '0.1.0'),
('context-cache', 'motus', 'Context Cache', 'Project memory and learned patterns', 'in_development', '0.1.0'),
('web-dashboard', 'motus-web', 'Web Dashboard', 'Real-time coordination visualization', 'in_development', '0.1.0');

-- =============================================================================
-- SEED STANDARDS (quality gates - the Motus difference)
-- =============================================================================

-- Release-level standards (apply to all releases)
INSERT INTO standards (id, name, description, level_key, check_type_key, check_command, failure_message, is_blocking) VALUES
('STD-REL-001', 'No blocklist terms', 'Ensure no CUDA, 4IR, DNA, hallucination terms', 'release', 'boolean',
 '! grep -rqiE "CUDA|4IR|\bDNA\b|hallucination" src/ README.md 2>/dev/null',
 'FAIL:blocklist - Found prohibited terms', 1),

('STD-REL-002', 'No personal paths', 'Ensure no personal identifiers', 'release', 'boolean',
 '! grep -rqiE "/Users/|/home/|C:\\\\Users\\\\|bnvoss|veritas" src/ tests/ 2>/dev/null',
 'FAIL:personal - Found personal identifiers', 1),

('STD-REL-003', 'No database files', 'Ensure no .db files in repo', 'release', 'boolean',
 '! find . -name "*.db" -not -path "./.git/*" 2>/dev/null | grep -q .',
 'FAIL:no-db - Found database files in repo', 1),

('STD-REL-004', 'No secrets', 'Ensure no API keys or secrets in code', 'release', 'boolean',
 '! grep -rqiE "api_key.*=|secret.*=|token.*=" src/ 2>/dev/null',
 'FAIL:secrets - Found hardcoded secrets', 1),

('STD-REL-005', 'Gitignore configured', 'Ensure .db and .env in gitignore', 'release', 'boolean',
 'grep -qE "\.db$|\.env|credentials" .gitignore',
 'FAIL:gitignore - Missing security patterns in .gitignore', 1),

('STD-REL-006', 'Non-destructive migrations', 'No DROP/DELETE/TRUNCATE in migrations', 'release', 'boolean',
 '! grep -qiE "DROP|DELETE FROM|TRUNCATE" migrations/*.sql 2>/dev/null',
 'FAIL:migrations - Found destructive SQL in migrations', 1),

('STD-REL-007', 'Branding correct', 'No loom or motus command references', 'release', 'boolean',
 '! grep -rqiE "loom|motus.command" src/ README.md',
 'FAIL:branding - Found deprecated branding', 1);

-- Product-level standards
INSERT INTO standards (id, name, description, level_key, check_type_key, check_command, failure_message, is_blocking) VALUES
('STD-PRD-001', 'All tests pass', 'pytest must pass', 'product', 'boolean',
 'python3 -m pytest tests/ -q --tb=no',
 'FAIL:tests - Test failures detected', 1),

('STD-PRD-002', 'Linting clean', 'ruff check must pass', 'product', 'boolean',
 'ruff check src/',
 'FAIL:lint - Linting errors detected', 1),

('STD-PRD-003', 'No security vulnerabilities', 'pip-audit must pass', 'product', 'boolean',
 'pip-audit',
 'FAIL:security - Security vulnerabilities detected', 1);

-- CR-level standards
INSERT INTO standards (id, name, description, level_key, check_type_key, failure_message, is_blocking) VALUES
('STD-CR-001', 'Separate review agent', 'Builder agent cannot review own CR', 'cr', 'manual',
 'FAIL:review - Same agent built and reviewed', 1),

('STD-CR-002', 'OODA close-loop', 'Must observe results after acting', 'cr', 'manual',
 'FAIL:ooda - No verification after implementation', 1);

-- Assign release standards to motus product
INSERT INTO standard_assignments (standard_id, entity_type, entity_id) VALUES
('STD-REL-001', 'product', 'motus'),
('STD-REL-002', 'product', 'motus'),
('STD-REL-003', 'product', 'motus'),
('STD-REL-004', 'product', 'motus'),
('STD-REL-005', 'product', 'motus'),
('STD-REL-006', 'product', 'motus'),
('STD-REL-007', 'product', 'motus'),
('STD-PRD-001', 'product', 'motus'),
('STD-PRD-002', 'product', 'motus'),
('STD-PRD-003', 'product', 'motus');

-- =============================================================================
-- DOWN
-- =============================================================================

-- Drop views
DROP VIEW IF EXISTS v_programs_summary;
DROP VIEW IF EXISTS v_standards_summary;
DROP VIEW IF EXISTS v_compliance_status;
DROP VIEW IF EXISTS v_active_charters;
DROP VIEW IF EXISTS v_roadmap_progress;
DROP VIEW IF EXISTS v_bugs_by_version;
DROP VIEW IF EXISTS v_open_crs;

-- Drop triggers
DROP TRIGGER IF EXISTS compliance_no_delete;
DROP TRIGGER IF EXISTS compliance_immutable;
DROP TRIGGER IF EXISTS entity_versions_no_delete;
DROP TRIGGER IF EXISTS entity_versions_immutable;
DROP TRIGGER IF EXISTS roadmap_version_capture;
DROP TRIGGER IF EXISTS bug_version_capture;
DROP TRIGGER IF EXISTS feature_version_capture;
DROP TRIGGER IF EXISTS product_version_capture;
DROP TRIGGER IF EXISTS cr_version_capture;
DROP TRIGGER IF EXISTS charter_singleton_enforce;

-- Drop compliance tables
DROP INDEX IF EXISTS idx_compliance_standard;
DROP INDEX IF EXISTS idx_compliance_result;
DROP INDEX IF EXISTS idx_compliance_release;
DROP INDEX IF EXISTS idx_compliance_entity;
DROP TABLE IF EXISTS compliance_results;

DROP INDEX IF EXISTS idx_assignments_standard;
DROP INDEX IF EXISTS idx_assignments_entity;
DROP TABLE IF EXISTS standard_assignments;

DROP INDEX IF EXISTS idx_standards_blocking;
DROP INDEX IF EXISTS idx_standards_level;
DROP TABLE IF EXISTS standards;

-- Drop releases
DROP INDEX IF EXISTS idx_releases_status;
DROP INDEX IF EXISTS idx_releases_type;
DROP INDEX IF EXISTS idx_releases_product;
DROP TABLE IF EXISTS releases;

-- Drop entity versions
DROP INDEX IF EXISTS idx_versions_latest;
DROP INDEX IF EXISTS idx_versions_entity;
DROP TABLE IF EXISTS entity_versions;

-- Drop charter docs
DROP INDEX IF EXISTS idx_charter_version;
DROP INDEX IF EXISTS idx_charter_type;
DROP INDEX IF EXISTS idx_charter_singleton;
DROP TABLE IF EXISTS charter_docs;

-- Drop bugs
DROP INDEX IF EXISTS idx_bugs_fix;
DROP INDEX IF EXISTS idx_bugs_severity;
DROP INDEX IF EXISTS idx_bugs_status;
DROP INDEX IF EXISTS idx_bugs_feature;
DROP TABLE IF EXISTS bugs;

-- Drop roadmap items
DROP INDEX IF EXISTS idx_roadmap_sort;
DROP INDEX IF EXISTS idx_roadmap_status;
DROP INDEX IF EXISTS idx_roadmap_phase;
DROP TABLE IF EXISTS roadmap_items;

-- Drop CR dependencies
DROP INDEX IF EXISTS idx_cr_dep_blocks;
DROP TABLE IF EXISTS cr_dependencies;

-- Drop change requests
DROP INDEX IF EXISTS idx_cr_target;
DROP INDEX IF EXISTS idx_cr_owner;
DROP INDEX IF EXISTS idx_cr_feature;
DROP INDEX IF EXISTS idx_cr_product;
DROP INDEX IF EXISTS idx_cr_status;
DROP TABLE IF EXISTS change_requests;

-- Drop features
DROP INDEX IF EXISTS idx_features_version;
DROP INDEX IF EXISTS idx_features_status;
DROP INDEX IF EXISTS idx_features_product;
DROP TABLE IF EXISTS features;

-- Drop products
DROP INDEX IF EXISTS idx_products_active;
DROP INDEX IF EXISTS idx_products_status;
DROP INDEX IF EXISTS idx_products_program;
DROP TABLE IF EXISTS products;

-- Drop programs
DROP INDEX IF EXISTS idx_programs_active;
DROP INDEX IF EXISTS idx_programs_type;
DROP TABLE IF EXISTS programs;

-- Delete terminology entries
DELETE FROM terminology WHERE domain IN (
    'product_status', 'feature_status', 'roadmap_phase',
    'roadmap_status', 'bug_severity', 'bug_status', 'charter_type',
    'program_type', 'release_type', 'release_status', 'standard_level', 'check_type'
);
