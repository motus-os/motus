# CR: Canonical Path Migration (.mc/ → .motus/)

**Decision**: `.motus/` is canonical
**Status**: Ready for execution
**Assigned**: Builder Agent
**Release**: v0.1.2

---

## Rationale

| Factor | `.mc/` | `.motus/` | Winner |
|--------|--------|-----------|--------|
| References in codebase | 37 | 108 | .motus/ |
| Brand alignment | Ambiguous | Clear | .motus/ |
| Config discovery | - | Already uses | .motus/ |
| Newer code | Legacy | Current | .motus/ |

**Decision owner**: Ben (2026-01-06)

---

## Phase 1: Deprecation Warning (v0.1.2)

### 1.1 Add migration utility

**File**: `packages/cli/src/motus/migration/path_migration.py`

```python
def check_legacy_path() -> Optional[str]:
    """Check for legacy .mc/ directory and warn."""
    legacy = Path.home() / ".mc"
    if legacy.exists():
        return (
            "DEPRECATION: ~/.mc/ detected. "
            "Motus now uses ~/.motus/ as canonical path. "
            "Run 'motus db migrate-path' to migrate. "
            "Support for ~/.mc/ will be removed in v0.2.0."
        )
    return None
```

### 1.2 Add deprecation gate

**File**: `scripts/gates/gate-path-001.sh`

```bash
#!/usr/bin/env bash
# GATE-PATH-001: No new .mc/ references in source

set -euo pipefail

# Allow legacy references in migration code only
ALLOWED_FILES=(
    "src/motus/migration/path_migration.py"
    "src/motus/config.py"  # Until Phase 2
)

# Check for .mc/ in source (excluding allowed files)
if grep -rn '\.mc/' packages/cli/src/motus/ \
    --include="*.py" \
    | grep -v "migration/path_migration.py" \
    | grep -v "# LEGACY:" \
    | grep -q .; then
    echo "FAIL: New .mc/ references found in source"
    exit 1
fi

echo "PASS: No new .mc/ references"
```

### 1.3 Update config.py

**File**: `packages/cli/src/motus/config.py:30`

```python
# BEFORE:
state_dir: Path = field(default_factory=lambda: Path.home() / ".mc")

# AFTER:
state_dir: Path = field(default_factory=lambda: Path.home() / ".motus")
```

### 1.4 Update tracer.py

**File**: `packages/cli/src/motus/tracer.py:60`

```python
# BEFORE:
# Traces stored at ~/.mc/traces/<session_id>.jsonl

# AFTER:
# Traces stored at ~/.motus/traces/<session_id>.jsonl
```

### 1.5 Add CLI migration command

**File**: `packages/cli/src/motus/cli/commands/db.py`

Add `motus db migrate-path` subcommand that:
- Copies `~/.mc/*` to `~/.motus/`
- Preserves file timestamps
- Validates migration success
- Optionally removes `~/.mc/` after confirmation

---

## Phase 2: Documentation Update (v0.1.2)

### 2.1 Files to update

| File | Change |
|------|--------|
| `packages/cli/docs/cli-reference.md` | All `.mc/` → `.motus/` |
| `packages/cli/docs/integration-guide.md` | Line 81: `.mc/` → `.motus/` |
| `packages/cli/docs/standards/userland-contract.md` | Line 66: `.mc/evidence/` → `.motus/evidence/` |
| `packages/cli/src/motus/scope.py` | Line 140-141: Exclude `.motus/` |
| `packages/cli/src/motus/checkpoint.py` | Line 137: Git clean excludes `.motus/` |

### 2.2 Bulk replacement command

```bash
# Dry run
grep -rln '\.mc/' packages/cli/docs/ packages/cli/src/motus/ \
  | xargs -I{} echo "Would update: {}"

# Execute (after review)
find packages/cli/docs packages/cli/src/motus -name "*.py" -o -name "*.md" \
  | xargs sed -i '' 's/\.mc\//\.motus\//g'
```

---

## Phase 3: Remove Deprecation (v0.2.0)

### 3.1 Remove legacy support

- Remove `check_legacy_path()` warning
- Remove migration command (or convert to error)
- Update GATE-PATH-001 to hard-fail on any `.mc/` reference

### 3.2 CHANGELOG entry

```markdown
### Breaking Changes

- **Path migration**: `~/.mc/` is no longer supported. All state is now stored in `~/.motus/`.
  Users who did not migrate in v0.1.x will need to manually move their data.
```

---

## Acceptance Criteria

### v0.1.2

- [ ] `config.py` uses `~/.motus/` as default state_dir
- [ ] Deprecation warning emitted when `~/.mc/` exists
- [ ] `motus db migrate-path` command works
- [ ] GATE-PATH-001 blocks new `.mc/` references
- [ ] All documentation references updated
- [ ] No test failures

### v0.2.0

- [ ] Legacy path support removed
- [ ] CHANGELOG documents breaking change
- [ ] Gate hard-fails on any `.mc/` reference

---

## Verification Commands

```bash
# Count remaining .mc/ references (should be 0 after Phase 2)
grep -rn '\.mc/' packages/cli/src/motus/ --include="*.py" | wc -l

# Verify config default
python3 -c "from motus.config import MotusConfig; print(MotusConfig().state_dir)"
# Expected: /Users/<user>/.motus

# Run path gate
bash scripts/gates/gate-path-001.sh

# Run all tests
cd packages/cli && pytest tests/ -x
```

---

*CR created: 2026-01-06*
*Decision: .motus/ canonical*
*Target: v0.1.2 (deprecation), v0.2.0 (removal)*
