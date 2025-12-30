# Motus Database Schema
Status: ACTIVE
Owner: DOCS_SPECS
Scope: Kernel schema overview and module index
Version: 0.1
Date: 2025-12-30

**Kernel Spec**: v0.1.3
**Database**: `~/.motus/coordination.db` (kernel.db deprecated alias)
**Engine**: SQLite

---

## Overview

Motus uses `~/.motus/coordination.db` as the single source of truth for kernel
state (v0.1.0 uses a single database). The schema is organized into:

1. **Kernel** - Planning plane + execution logs (attempts, decisions, evidence,
   blockers, leases).
2. **Program Management** - Products, releases, standards, roadmap metadata.
3. **Userland (planned)** - User preferences and local customization (future).

## Connection Configuration

All connections use standardized PRAGMA settings:

```sql
PRAGMA journal_mode = WAL;       -- Concurrent reads during writes
PRAGMA synchronous = NORMAL;     -- Balance safety and speed
PRAGMA foreign_keys = ON;        -- Referential integrity
PRAGMA busy_timeout = 5000;      -- 5s contention handling
PRAGMA cache_size = -64000;      -- 64MB cache
```

## Schema Modules

| Module | Source | Purpose |
|--------|--------|---------|
| Kernel DB | [kernel.md](./kernel.md) | Kernel tables, views, triggers in coordination.db |
| Program Management | [program-management.md](./program-management.md) | Products, releases, standards, roadmap metadata |
| Userland DB (planned) | [userland.md](./userland.md) | User preferences and local customization |

## Design Principles

### Soft Deletes
All tables use `deleted_at TEXT` for soft deletion:
- Active records: `WHERE deleted_at IS NULL`
- Partial indexes: `CREATE INDEX ... WHERE deleted_at IS NULL`
- No CASCADE deletes - RESTRICT prevents orphans

### Immutable Audit Trail
Certain tables are protected from modification:
- `compliance_results` - Audit of standard checks
- `entity_versions` - Change history snapshots

Triggers enforce immutability:
```sql
CREATE TRIGGER audit_log_immutable
BEFORE UPDATE ON audit_log
BEGIN
    SELECT RAISE(ABORT, 'Audit log is immutable');
END;
```

### Terminology Pattern
Status/type fields use lookup keys:
- `status_key TEXT NOT NULL` references terminology table
- Validation is application-level (not FK - keys are domain-scoped)

---

## Quick Reference

### Kernel Tables (v0.1.3)
| Table | Purpose |
|-------|---------|
| roadmap_items | Planning plane (work intent) |
| attempts | Execution instances |
| decisions | Append-only governance decisions |
| evidence | Typed + hashed artifacts |
| blockers | Runtime execution blockers |
| leases | Resource coordination (LeaseStore runtime table) |

### Program Management
See [program-management.md](./program-management.md) for products, releases,
standards, and roadmap metadata.

### Kernel Details
See [kernel.md](./kernel.md) for the full table/view/trigger inventory.
