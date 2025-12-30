# Program Management Schema
Status: ACTIVE
Owner: DOCS_SPECS
Scope: Program management schema tables and relationships
Version: 0.1
Date: 2025-12-30

**Migration**: 005_program_management.sql
**Version**: 5

---

## Entity Hierarchy

```
Program (software, content, infrastructure)
  └── Product (motus, motus-web)
       ├── Feature (coordination-api, policy-gates)
       │    └── Bug (version-specific defects)
       └── Release (v0.1.0, blog posts, deploys)
            └── Compliance Results (standard checks)

Change Requests → link to Product/Feature
Roadmap Items → link to Feature/CR
Standards → apply at any level
```

---

## Tables

### programs
Top-level containers for related work.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | TEXT | PRIMARY KEY | 'motus-cli', 'bens-linkedin' |
| name | TEXT | NOT NULL | Display name |
| description | TEXT | | |
| type_key | TEXT | NOT NULL DEFAULT 'software' | program_type terminology |
| status_key | TEXT | NOT NULL DEFAULT 'active' | product_status terminology |
| owner | TEXT | | Agent or person ID |
| created_at | TEXT | NOT NULL DEFAULT (datetime('now')) | |
| updated_at | TEXT | NOT NULL DEFAULT (datetime('now')) | |
| deleted_at | TEXT | | Soft delete |

### products
Deployable units within programs.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | TEXT | PRIMARY KEY | 'motus', 'motus-web' |
| program_id | TEXT | NOT NULL, FK | Parent program |
| name | TEXT | NOT NULL | Display name |
| description | TEXT | | |
| status_key | TEXT | NOT NULL DEFAULT 'active' | product_status terminology |
| version | TEXT | NOT NULL DEFAULT '0.0.0' | Current version |
| repository_url | TEXT | | GitHub URL |
| created_at | TEXT | NOT NULL | |
| updated_at | TEXT | NOT NULL | |
| deleted_at | TEXT | | Soft delete |

### features
Capabilities within products.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | TEXT | PRIMARY KEY | 'coordination-api' |
| product_id | TEXT | NOT NULL, FK | Parent product |
| name | TEXT | NOT NULL | Display name |
| description | TEXT | | |
| status_key | TEXT | NOT NULL DEFAULT 'planned' | feature_status terminology |
| version | TEXT | | Feature version |
| introduced_in | TEXT | | Product version added |
| deprecated_in | TEXT | | Product version deprecated |
| created_at | TEXT | NOT NULL | |
| updated_at | TEXT | NOT NULL | |
| deleted_at | TEXT | | Soft delete |

### change_requests
Work items (enhancements, bugs, specs).

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | TEXT | PRIMARY KEY | 'CR-2025-12-26-001' |
| title | TEXT | NOT NULL | |
| description | TEXT | | |
| status_key | TEXT | NOT NULL DEFAULT 'queue' | cr_status terminology |
| type_key | TEXT | NOT NULL DEFAULT 'enhancement' | cr_type terminology |
| size | TEXT | NOT NULL DEFAULT 'M', CHECK (S/M/L/XL) | Effort estimate |
| owner | TEXT | | Assigned agent/person |
| product_id | TEXT | FK | Target product |
| feature_id | TEXT | FK | Target feature |
| target_version | TEXT | | Planned release |
| completed_version | TEXT | | Actual release |
| created_at | TEXT | NOT NULL | |
| updated_at | TEXT | NOT NULL | |
| started_at | TEXT | | Work began |
| completed_at | TEXT | | Work finished |
| deleted_at | TEXT | | Soft delete |

### cr_dependencies
Directed graph of CR relationships.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| cr_id | TEXT | NOT NULL, FK, PK | Source CR |
| depends_on_id | TEXT | NOT NULL, FK, PK | Target CR |
| dependency_type | TEXT | NOT NULL, CHECK | 'blocks', 'related', 'supersedes' |
| created_at | TEXT | NOT NULL | |

CHECK: `cr_id != depends_on_id` (no self-reference)

### roadmap_items
Phase-based planning.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | TEXT | PRIMARY KEY | 'RI-001' |
| phase_key | TEXT | NOT NULL | roadmap_phase terminology |
| title | TEXT | NOT NULL | |
| description | TEXT | | |
| status_key | TEXT | NOT NULL DEFAULT 'pending' | roadmap_status terminology |
| owner | TEXT | | Assigned agent |
| feature_id | TEXT | FK | Linked feature |
| cr_id | TEXT | FK | Linked CR |
| target_date | TEXT | | Target completion |
| completed_at | TEXT | | Actual completion |
| sort_order | INTEGER | NOT NULL DEFAULT 0 | Display order |
| created_at | TEXT | NOT NULL | |
| updated_at | TEXT | NOT NULL | |
| deleted_at | TEXT | | Soft delete |

### bugs
Version-specific defects.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | TEXT | PRIMARY KEY | 'BUG-2025-12-26-001' |
| title | TEXT | NOT NULL | |
| description | TEXT | | |
| feature_id | TEXT | NOT NULL, FK | Affected feature |
| feature_version | TEXT | NOT NULL | Version with bug |
| severity_key | TEXT | NOT NULL DEFAULT 'medium' | bug_severity terminology |
| status_key | TEXT | NOT NULL DEFAULT 'open' | bug_status terminology |
| reported_by | TEXT | | |
| assigned_to | TEXT | | |
| fix_cr_id | TEXT | FK | CR that fixes this |
| fixed_in_version | TEXT | | Version with fix |
| created_at | TEXT | NOT NULL | |
| updated_at | TEXT | NOT NULL | |
| resolved_at | TEXT | | |
| deleted_at | TEXT | | Soft delete |

### releases
Versions, posts, campaigns, deploys.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | TEXT | PRIMARY KEY | 'v0.1.0', 'post-2025-12-26-001' |
| product_id | TEXT | NOT NULL, FK | Parent product |
| type_key | TEXT | NOT NULL DEFAULT 'version' | release_type terminology |
| name | TEXT | NOT NULL | Display name |
| description | TEXT | | |
| status_key | TEXT | NOT NULL DEFAULT 'pending' | release_status terminology |
| target_date | TEXT | | Planned date |
| published_at | TEXT | | Actual date |
| external_url | TEXT | | PyPI, LinkedIn, etc. |
| created_at | TEXT | NOT NULL | |
| updated_at | TEXT | NOT NULL | |
| deleted_at | TEXT | | Soft delete |

### standards
Quality gates at every level.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | TEXT | PRIMARY KEY | 'STD-REL-001' |
| name | TEXT | NOT NULL | |
| description | TEXT | | |
| doc_path | TEXT | | Path to detailed standard doc |
| level_key | TEXT | NOT NULL | standard_level terminology |
| check_type_key | TEXT | NOT NULL | check_type terminology |
| check_command | TEXT | | Bash for boolean/pattern |
| check_pattern | TEXT | | Regex for pattern check |
| threshold_min | REAL | | For threshold checks |
| threshold_max | REAL | | |
| failure_message | TEXT | NOT NULL | Error message |
| is_blocking | INTEGER | NOT NULL DEFAULT 1 | Blocks release |
| sort_order | INTEGER | NOT NULL DEFAULT 0 | |
| created_at | TEXT | NOT NULL | |
| updated_at | TEXT | NOT NULL | |
| deleted_at | TEXT | | Soft delete |

### compliance_results
Immutable audit trail of standard checks.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | |
| standard_id | TEXT | NOT NULL, FK | Standard checked |
| entity_type | TEXT | NOT NULL | 'program', 'product', etc. |
| entity_id | TEXT | NOT NULL | Entity checked |
| release_id | TEXT | FK | Which release |
| result | TEXT | NOT NULL, CHECK | 'pass', 'fail', 'skip', 'error' |
| result_value | TEXT | | Actual value (threshold) |
| error_message | TEXT | | |
| checked_by | TEXT | NOT NULL | 'agent:builder-1', 'system' |
| checked_at | TEXT | NOT NULL DEFAULT (datetime('now')) | |

**Immutable**: UPDATE/DELETE triggers prevent modification.

### charter_docs
Singleton documents (one active per type).

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | TEXT | PRIMARY KEY | 'charter-roadmap-v2.1' |
| doc_type_key | TEXT | NOT NULL | charter_type terminology |
| version | TEXT | NOT NULL | Document version |
| title | TEXT | NOT NULL | |
| content_hash | TEXT | NOT NULL | SHA-256 of content |
| file_path | TEXT | | Path to .md file |
| is_active | INTEGER | NOT NULL DEFAULT 1 | Current version |
| approved_by | TEXT | | |
| approved_at | TEXT | | |
| created_at | TEXT | NOT NULL | |
| updated_at | TEXT | NOT NULL | |
| deleted_at | TEXT | | Soft delete |

**Singleton enforced**: UNIQUE INDEX on `(doc_type_key) WHERE is_active = 1`

### entity_versions
Immutable change history snapshots.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | |
| entity_type | TEXT | NOT NULL | 'product', 'feature', 'cr', 'bug' |
| entity_id | TEXT | NOT NULL | |
| version | INTEGER | NOT NULL | Auto-increment per entity |
| data | TEXT | NOT NULL | JSON snapshot |
| changed_by | TEXT | NOT NULL | |
| change_reason | TEXT | | |
| created_at | TEXT | NOT NULL DEFAULT (datetime('now')) | |

UNIQUE: `(entity_type, entity_id, version)`

**Immutable**: UPDATE/DELETE triggers prevent modification.

---

## Terminology Domains

| Domain | Values | Used By |
|--------|--------|---------|
| program_type | software, content, infrastructure | programs.type_key |
| product_status | active, maintenance, deprecated, archived | programs, products |
| feature_status | planned, in_development, beta, stable, deprecated | features |
| cr_status | queue, in_progress, review, done | change_requests |
| cr_type | enhancement, bugfix, spec, chore | change_requests |
| roadmap_phase | phase_a, phase_b, phase_c, phase_d, phase_e, post_launch | roadmap_items |
| roadmap_status | pending, in_progress, blocked, completed, deferred | roadmap_items |
| bug_severity | critical, high, medium, low | bugs |
| bug_status | open, confirmed, in_progress, fixed, verified, wont_fix | bugs |
| release_type | version, post, campaign, deploy | releases |
| release_status | pending, in_progress, ready, published, archived | releases |
| charter_type | roadmap, ethos, release_checklist | charter_docs |
| standard_level | program, product, feature, release, cr | standards |
| check_type | boolean, threshold, pattern, manual | standards |
