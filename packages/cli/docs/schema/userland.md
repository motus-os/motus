# Userland Database Schema (Planned)

**Database**: `~/.motus/userland.db`
**Status**: Planned (not yet extracted from coordination.db)

---

## Scope

Userland data captures per-user customization and local operating context. The
tables below currently live in `~/.motus/coordination.db` and are candidates
for extraction when userland.db is introduced.

---

## Planned Tables (Currently in coordination.db)

| Table | Purpose |
|-------|---------|
| preferences | User preferences and toggles |
| skills | Skill definitions and metadata |
| ground_rules | Local operating constraints |
| learned_patterns | Learned heuristics and behaviors |
| detected_patterns | Observed pattern registry |

---

## Views

No userland-specific views are defined yet.

---

## Triggers

When extracted, preserve audit timestamp helpers:
`*_audit_insert` and `*_updated_at` triggers for preferences, skills,
ground_rules, learned_patterns, and detected_patterns.
