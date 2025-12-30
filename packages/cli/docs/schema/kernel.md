# Kernel Database Schema

**Database**: `~/.motus/coordination.db` (kernel.db deprecated alias)
**Spec Reference**: `.ai/handoffs/KERNEL-SCHEMA.md`
**Migrations**: `migrations/*.sql` (plus `schema_version` from migration runner)

---

## Scope

The kernel database is the authoritative source of truth for coordination,
planning, and governance. Program management tables are documented in
[program-management.md](./program-management.md).

---

## Tables

### Governance (KERNEL-SCHEMA)
| Table | Purpose | Notes |
|-------|---------|-------|
| compiled_contracts | Immutable compiled contract snapshots | No update/delete triggers |
| attempts | Execution instances for work items | Enforces claim + evidence rules |
| decisions | Append-only governance decisions | Immutable via triggers |
| evidence | Typed + hashed artifacts | Immutable via triggers |
| blockers | Runtime execution blockers | Resolution requires evidence/waiver |
| work_required_capabilities | Normalized capabilities required by work | PK on (work_id, capability_id) |

### Legacy Kernel (CLI compatibility)
| Table | Purpose | Notes |
|-------|---------|-------|
| kernel_decisions | Legacy decision log | Immutable via triggers |
| kernel_evidence | Legacy evidence log | Immutable via triggers |
| kernel_outcomes | Legacy outcome log | Immutable via triggers |

### Roadmap and Planning
| Table | Purpose | Notes |
|-------|---------|-------|
| roadmap_items | Planning items with lifecycle status | Core planning table |
| roadmap_dependencies | Directed dependencies between roadmap items | Enforces no cycles |
| roadmap_assignments | Agent assignments for roadmap items | Cascades to prerequisites |
| assignment_prerequisites | Tracking prerequisite claims | Auto-resolves on completion |
| plan_events | High-level plan events for governance | Append-only |
| claims | Policy claims for deploy gating | Used by v_can_deploy views |
| deployment_events | Deploy events with gating | Enforced by deploy gate trigger |

### LeaseStore (Coordination)
| Table | Purpose | Notes |
|-------|---------|-------|
| leases | Resource coordination leases | Created on demand by LeaseStore |
| events | Lease lifecycle event log | Created on demand by LeaseStore |

### Program Management (shared)
See [program-management.md](./program-management.md) for these tables:
programs, products, features, releases, change_requests, cr_dependencies,
bugs, standards, standard_assignments, compliance_results, charter_docs,
entity_versions.

### System and Policy
| Table | Purpose | Notes |
|-------|---------|-------|
| instance_config | Instance-level key/value settings | Audit timestamps enforced |
| terminology | Canonical terminology dictionary | Audit timestamps enforced |
| audit_log | Immutable audit trail | No update/delete triggers |
| resource_quotas | Quota configuration | Audit timestamps enforced |
| idempotency_keys | Request de-duplication | Audit timestamps enforced |
| health_check_results | Health checks (rolling window) | Cleanup trigger |
| circuit_breakers | Circuit breaker state | Audit timestamps enforced |
| extension_points | Plugin/handler registry | Minified boolean columns |
| metrics | Internal performance metrics | Minified boolean columns |
| schema_version | Migration history | Created by migration runner |

### Sessions and Cache
| Table | Purpose |
|-------|---------|
| sessions | Session metadata |
| session_cache_state | Cached session indices |
| session_event_cache | Event cache entries |
| session_file_cache | File cache entries |

### Patterns and Userland Candidates
| Table | Purpose | Notes |
|-------|---------|-------|
| learned_patterns | Learned behaviors and heuristics | Candidate for userland.db |
| detected_patterns | Observed patterns | Candidate for userland.db |
| ground_rules | Ground rules and constraints | Candidate for userland.db |
| skills | Skill definitions | Candidate for userland.db |
| preferences | User preferences | Candidate for userland.db |

---

## Views

### Roadmap and Dependency Views
| View | Purpose |
|------|---------|
| v_ready_items | Items ready for work (no blockers) |
| v_blocked_items | Items blocked by dependencies |
| v_dependency_graph | Flattened dependency edges |
| v_prerequisite_chain | Ordered prerequisite chain for an item |
| v_assignment_with_prerequisites | Assignments with prerequisite status |
| v_unassigned_prerequisites | Open prerequisites without assignments |
| v_next_rank | Next rank sequence for roadmap ordering |
| v_roadmap_with_deps | Roadmap items joined to dependency counts |
| v_roadmap_progress | Progress summary by phase |
| v_missing_prereqs | Missing prerequisite matrix for items |

### Claims and Deploy Views
| View | Purpose |
|------|---------|
| v_can_deploy | Deploy readiness summary |
| v_claims_needing_tests | Claims missing tests |
| v_deploy_blockers | Claims blocking deploy |

### Program Management Views
| View | Purpose |
|------|---------|
| v_open_crs | Change requests in active states |
| v_bugs_by_version | Bugs grouped by feature version |
| v_active_charters | Active charter docs |
| v_compliance_status | Release compliance rollups |
| v_standards_summary | Standards with assignment counts |
| v_programs_summary | Program summary with product counts |

---

## Triggers

### Kernel Governance Enforcement
- attempts_no_double_claim
- attempts_no_claim_blocked
- attempts_handoff_requires_reason
- attempts_completion_requires_evidence
- attempts_blocked_requires_blocker
- blockers_resolution_immutable
- blockers_resolution_requires_justification
- compiled_contracts_no_update
- compiled_contracts_no_delete

### Immutability
- audit_log_immutable / audit_log_no_delete
- compliance_immutable / compliance_no_delete
- entity_versions_immutable / entity_versions_no_delete
- decisions_no_update / decisions_no_delete
- evidence_no_update / evidence_no_delete
- kernel_decisions_no_update / kernel_decisions_no_delete
- kernel_evidence_no_update / kernel_evidence_no_delete
- kernel_outcomes_no_update / kernel_outcomes_no_delete

### Roadmap Enforcement and Audit
- roadmap_dep_no_cycles
- roadmap_status_check_deps
- roadmap_dep_audit_insert
- roadmap_assignment_audit
- roadmap_assignment_cascade
- roadmap_prereq_resolved
- enforce_completed_immutable
- enforce_phase_limit
- enforce_deploy_gate

### Version Capture
- cr_version_capture
- product_version_capture
- feature_version_capture
- bug_version_capture
- roadmap_version_capture

### Other
- charter_singleton_enforce
- health_check_cleanup

### Audit Timestamp Helpers
`*_audit_insert` and `*_updated_at` triggers exist for:
circuit_breakers, detected_patterns, ground_rules, health_check_results,
idempotency_keys, instance_config, learned_patterns, preferences,
resource_quotas, session_cache_state, session_event_cache, session_file_cache,
sessions, skills, terminology.
