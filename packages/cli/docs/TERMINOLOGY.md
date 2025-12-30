# Motus Terminology

> Canonical reference for Motus terminology. Single source of truth.
> Status: ACTIVE
> Last Updated: 2025-12-29

---

## Core Concepts

| Term | Definition | Example |
|------|------------|---------|
| Work Compiler | The kernel loop that transforms work into verified outcomes | claim -> execute -> evidence -> release |
| Phase | A major stage of work with clear boundaries and exit criteria | Phase 0: Reconciliation, Phase A: Monorepo Setup |
| Mission | A group of parallelizable tasks within a phase, sharing a common objective | Phase 0, Mission 1: Reconciliation Foundation |
| Planning Item | Any trackable unit of work with status and ownership | RI-A-001, P0-025, CR-2025-12-29-example |
| Change Request (CR) | Discrete work item requiring review | CR-2025-12-29-api-design |
| Roadmap Item | Planning item in the roadmap with phase assignment | RI-B-003 |

---

## The Three Planes

| Term | Definition | Purpose |
|------|------------|---------|
| Control Plane | Where decisions are made | Policy, configuration, governance |
| Ops Plane | Where coordination happens | Claims, leases, scheduling |
| Data Plane | Where work happens | Execution, traces, evidence |

---

## The Three Primitives

| Term | Definition | What It Serves |
|------|------------|----------------|
| Event Log | Immutable record of actions, decisions, outcomes | Evidence, Audit, Knowledge capture |
| Lease | Time-bounded capability + baseline snapshot | Coordination, Rollback, Recovery |
| Lens | Assembled knowledge for THIS task | Context, Memory, Transplant |

---

## The 6-Call API

The canonical Work Compiler protocol. See `.ai/specs/6-CALL-API-FACADE.md` for full specification.

| Call | Purpose |
|------|---------|
| `claim_work` | Reserve a roadmap item, get lease |
| `get_context` | Assemble lens: task, standards, file policy, dependencies |
| `put_outcome` | Register primary deliverable(s) produced |
| `record_evidence` | Store verification artifacts (tests, diffs, logs) |
| `record_decision` | Append-only decision logging (why X, not Y) |
| `release_work` | End lease, record disposition (complete/blocked/abandoned) |

### Extensions (Not Core Protocol)

| Call | Purpose | Status |
|------|---------|--------|
| `peek` | Scout resources without locking | Planned |
| `claim_additional` | Expand scope without losing context | Planned |
| `force_release` | Human override (audited) | Planned |

---

## Artifact Types

| Term | Definition |
|------|------------|
| Flight Rule | Pre-computed decision (no thinking required) |
| Playbook | Domain guidance with MUST/SHOULD/MAY rules |
| ADR | Architectural Decision Record |

---

## Status Values

### CR Status

| Key | Display | Meaning |
|-----|---------|---------|
| `queue` | Queue | Not yet started |
| `in_progress` | In Progress | Active work |
| `review` | Review | Awaiting review |
| `done` | Done | Completed |

### Feature Status

| Key | Display | Meaning |
|-----|---------|---------|
| `planned` | Planned | Not yet started |
| `in_development` | In Development | Active work |
| `beta` | Beta | Testing phase |
| `stable` | Stable | Production ready |
| `deprecated` | Deprecated | Being phased out |

---

## Legacy Concept Mappings

| Legacy Concept | Motus Equivalent | Source | Notes |
|----------------|------------------|--------|-------|
| Decision-action loop | Work Compiler | Military/strategy | Work Loop maps to the compiler loop |
| Risk/Action/Issue/Decision logs | Planning Items | Project management | Tracking moves into planning items |
| Large work container for stories | Phase | Agile/Scrum | Phase = container for work |
| Sprint | (not used) | Agile/Scrum | Motus uses continuous flow, not time-boxed sprints |
| Story | Planning Item | Agile/Scrum | User story maps to CR or roadmap item |
| Backlog | Roadmap | Agile/Scrum | Prioritized list of work |

---

## Deprecated Terms

| Term | Replacement | Reason | Deprecated |
|------|-------------|--------|------------|
| kernel.db | coordination.db | v0.1.0 uses single database | 2025-12 |
| planning.db | coordination.db | Future extraction, not current | 2025-12 |
| motus.db | coordination.db | Fossil from rename chain | 2025-12-29 |
| DNA | Flight Rule | Terminology alignment | 2025-12-19 |
| Skill Pack | Playbook | Terminology alignment | 2025-12-19 |

---

## Database Architecture

### Kernel (Authoritative)

`~/.motus/coordination.db` - Single source of truth. SQLite database containing:

| Table | Purpose |
|-------|---------|
| `roadmap_items` | All work items with status, phase, dependencies |
| `terminology` | Canonical term definitions (this document's source) |
| `audit_log` | Immutable change history |

Query example:
```bash
sqlite3 ~/.motus/coordination.db "SELECT id, title, status_key FROM roadmap_items WHERE phase_key='phase_0' AND deleted_at IS NULL"
```

### Cache (Non-Authoritative)

`~/.motus/context_cache.db` - Derived data, can be cleared and rebuilt.

| Table | Purpose |
|-------|---------|
| `resource_specs` | Observed file/resource specifications |
| `policy_bundles` | Observed policy configurations |
| `tool_specs` | Observed tool definitions |
| `outcomes` | Recorded outcomes (rebuild from events if lost) |

**Key property:** Clearing this database loses no authoritative data. All content can be rebuilt from source files or coordination.db events.

### Future Pattern (v0.2.0+)

| Database | Purpose | Status |
|----------|---------|--------|
| `~/.motus/userland.db` | User customizations, preferences | Planned |
| `~/.motus/modules/<name>.db` | Per-module state (optional) | Planned |

---

## Naming Conventions

| Type | Pattern | Example |
|------|---------|---------|
| Phase | `phase_X` (lowercase letter) | phase_0, phase_a, phase_b |
| Roadmap Item | `RI-{phase}-{number}` | RI-A-001, RI-B-003 |
| Phase 0 Task | `P0-{number}` | P0-025 |
| Change Request | `CR-{date}-{slug}` | CR-2025-12-29-api-design |

---

*No jargon without definition. No external terms without mapping.*
