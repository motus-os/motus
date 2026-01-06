# v0.1.2 Builder Agent Handoff

**Date**: 2026-01-06
**From**: Orchestrator (Opus)
**To**: Builder Agent
**Purpose**: Complete remaining v0.1.2 features

---

## Current State

### Commits Landed
```
968c798 docs(architecture): Add Ecosystem Agnostic principle (ADR-005)
a9011ea Add userland contract and module registry tooling
3e94ffc Update internal gate leak checks
ae5e4ea Add website content standards and CI checks
bcf9fd0 Remove motus-internal from conflict messaging
765f8ca chore(gates): consolidate release gate scripts
6e23fb8 chore(standards): merge motus-standards into canonical docs
```

### Uncommitted Work (needs commit)
```
packages/cli/docs/implementation/base-userland.md
packages/cli/scripts/ci/check_gates_registry.py
packages/cli/src/motus/cli/commands/gates.py
packages/cli/src/motus/commands/gates_cmd.py
packages/cli/src/motus/data/
scripts/gates/gate-roadmap-001.sh
```

### Roadmap Status
| ID | Title | Status |
|----|-------|--------|
| RI-CONS-001 | Merge motus-standards | ✓ completed |
| RI-CONS-002 | Consolidate migrations + gates | ✓ completed |
| RI-CONS-003 | Rename motus-command to motus-internal | ✓ completed |
| RI-ENV-001 | Align gate env vars | ✓ completed |
| RI-PATH-004 | Archive motus-website | ✓ completed |
| RI-POST-001 | Retire motus-command | ✓ completed |
| RI-BASE-001 | Base Userland Contract | **needs DB update** |
| RI-BASE-002 | Module registry + CLI | **needs DB update** |
| RI-BASE-003 | Gate registry | **needs commit + DB update** |
| RI-BASE-004 | Roadmap hygiene gates | **needs commit + DB update** |
| RI-SCR-001 | Scratch file store | **pending** |
| RI-SCR-002 | Scratch promote to roadmap | **pending** |

---

## Task 1: Commit Uncommitted Work

```bash
cd /Users/ben/GitHub/motus

# Commit gates CLI
git add packages/cli/src/motus/cli/commands/gates.py \
        packages/cli/src/motus/commands/gates_cmd.py \
        packages/cli/scripts/ci/check_gates_registry.py \
        scripts/gates/gate-roadmap-001.sh

git commit -m "feat(cli): Add motus gates list/show commands (RI-BASE-003)"

# Commit remaining base userland files
git add packages/cli/docs/implementation/base-userland.md \
        packages/cli/src/motus/data/

git commit -m "docs(standards): Add base userland implementation guide"

# Commit modified files
git add -u
git commit -m "chore: Wire gates CLI into dispatch and update tests"
```

---

## Task 2: Update Roadmap DB

```bash
sqlite3 ~/.motus/coordination.db "
UPDATE roadmap_items SET status_key = 'completed'
WHERE id IN ('RI-BASE-001', 'RI-BASE-002', 'RI-BASE-003', 'RI-BASE-004');
"
```

Verify:
```bash
sqlite3 ~/.motus/coordination.db "
SELECT id, status_key FROM roadmap_items WHERE id LIKE 'RI-BASE-%';
"
```

---

## Task 3: Implement RI-SCR-001 (Scratch File Store)

### Requirements
- Store scratch files in `~/.motus/scratch/`
- Index in coordination.db: `scratch_files` table
- CLI: `motus scratch list`, `motus scratch add <file>`, `motus scratch show <id>`

### Schema
```sql
CREATE TABLE IF NOT EXISTS scratch_files (
    id TEXT PRIMARY KEY,
    path TEXT NOT NULL,
    description TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    promoted_to TEXT,  -- roadmap item ID if promoted
    status TEXT DEFAULT 'active'  -- active, promoted, archived
);
```

### Acceptance Criteria
- [ ] `motus scratch add README.md --desc "Draft readme"` creates entry
- [ ] `motus scratch list` shows all scratch files
- [ ] `motus scratch show SCR-001` shows details
- [ ] Files copied to `~/.motus/scratch/<id>/`
- [ ] Tests in `tests/test_scratch_cmd.py`

---

## Task 4: Implement RI-SCR-002 (Scratch Promote to Roadmap)

### Requirements
- CLI: `motus scratch promote <scratch_id> --roadmap-id <RI-xxx>`
- Updates `promoted_to` field
- Creates/links to roadmap item

### Acceptance Criteria
- [ ] `motus scratch promote SCR-001 --roadmap-id RI-NEW-001` works
- [ ] Scratch status changes to `promoted`
- [ ] Roadmap item created if `--create` flag
- [ ] Tests pass

---

## Task 5: Website Proof Ledger Population

### Location
`/Users/ben/GitHub/motus/packages/website/standards/proof-ledger.json`

### Claims to Add
```json
{
  "claims": [
    {
      "id": "token-reduction-95",
      "claim": "Up to 95% fewer context tokens",
      "status": "verified",
      "evidence_path": "docs/proof/token-reduction-benchmark.md",
      "methodology": "4-scenario benchmark, reproducible",
      "last_verified": "2026-01-05",
      "commit_sha": "9d8a88a"
    },
    {
      "id": "token-reduction-88-avg",
      "claim": "Average 88% reduction across usage patterns",
      "status": "verified",
      "evidence_path": "docs/proof/token-reduction-benchmark.md",
      "methodology": "Mean of 4 scenarios",
      "last_verified": "2026-01-05",
      "commit_sha": "9d8a88a"
    },
    {
      "id": "ecosystem-agnostic",
      "claim": "Works with Claude, Codex, Gemini, and local agents",
      "status": "verified",
      "evidence_path": "packages/cli/src/motus/ingestors/",
      "methodology": "Ingestor exists for each ecosystem",
      "last_verified": "2026-01-06",
      "commit_sha": "968c798"
    },
    {
      "id": "six-call-api",
      "claim": "6-call API for agent accountability",
      "status": "verified",
      "evidence_path": "packages/cli/docs/standards/userland-contract.md",
      "methodology": "API surface documented and tested",
      "last_verified": "2026-01-06",
      "commit_sha": "a9011ea"
    }
  ]
}
```

### Validation
```bash
python3 packages/website/scripts/ci/check_content_standard.py
```

---

## Task 6: Run All Gates Before Marking Complete

```bash
cd /Users/ben/GitHub/motus

# Package gates
bash scripts/gates/gate-pkg-001.sh
bash scripts/gates/gate-repo-001.sh
bash scripts/gates/gate-src-001.sh

# Tests
cd packages/cli && python3 -m pytest tests/ -x

# Website checks
python3 packages/website/scripts/ci/check_content_standard.py
python3 packages/website/scripts/ci/check_tailwind_arbitrary.py

# New gates
python3 packages/cli/scripts/ci/check_gate_registry.py
python3 packages/cli/scripts/ci/check_roadmap_hygiene.py --strict
```

---

## Definition of Done for v0.1.2

| Criterion | Check |
|-----------|-------|
| All RI-BASE-* completed | `sqlite3 ~/.motus/coordination.db "SELECT * FROM roadmap_items WHERE id LIKE 'RI-BASE-%'"` |
| All RI-SCR-* completed | `sqlite3 ~/.motus/coordination.db "SELECT * FROM roadmap_items WHERE id LIKE 'RI-SCR-%'"` |
| Proof ledger has ≥4 verified claims | `cat packages/website/standards/proof-ledger.json` |
| All gates pass | `scripts/gates/run-all-gates.sh` |
| No uncommitted work | `git status --short` returns empty |
| Tests pass | `pytest tests/ -x` |

---

## Key Files Reference

| Purpose | Path |
|---------|------|
| Userland contract | `packages/cli/docs/standards/userland-contract.md` |
| Module registry | `packages/cli/docs/standards/module-registry.yaml` |
| Gate registry | `packages/cli/docs/standards/gates.yaml` |
| ADR-005 (Ecosystem Agnostic) | `packages/cli/docs/adr/ADR-005-ecosystem-agnostic-principle.md` |
| Proof ledger | `packages/website/standards/proof-ledger.json` |
| Content standard | `packages/website/CONTENT-STANDARD.md` |

---

## Core Principle (ADR-005)

> "Codex knows what Codex did. Claude knows what Claude did. **Motus knows what everyone did.**"

Motus is ecosystem agnostic. We ingest, we don't compete. Good fences make good neighbors.

---

*Handoff created: 2026-01-06*
*Next review: After RI-SCR-001/002 complete*
