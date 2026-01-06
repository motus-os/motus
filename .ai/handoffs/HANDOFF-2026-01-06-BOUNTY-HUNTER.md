# Bounty Hunter Handoff

**Date**: 2026-01-06
**From**: Crucible Team (Opus)
**To**: Defect Resolution Agents
**Purpose**: Document and track defects found during v0.1.2 crucible testing

---

## Executive Summary

The crucible (4-agent attack testing) completed with the following results:
- **Gate Runner**: 2 critical blockers found (1 fixed)
- **Security Scanner**: Secure (minor findings)
- **Fresh-Eyes**: 4/10 clarity score
- **Proof Auditor**: 3/3 claims verified

This handoff documents all defects as CRs for resolution.

---

## DEFECT CRs

### CR-DEFECT-001: [FIXED] Duplicate gates_parser in registry.py

**Status**: RESOLVED
**Severity**: CRITICAL (SyntaxError)
**File**: `packages/cli/src/motus/cli/commands/registry.py`
**Commit**: Pending

**Issue**: Duplicate import, dataclass field, function call, and keyword argument for `gates_parser` caused SyntaxError.

**Resolution**: Removed all duplicates:
- Line 17-18: Duplicate import removed
- Line 46-47: Duplicate dataclass field removed
- Line 93: Duplicate `register_gates_parsers()` call removed
- Line 106-107: Duplicate keyword argument removed

---

### CR-DEFECT-002: [CRITICAL] .mc/ vs .motus/ Path Inconsistency

**Status**: OPEN
**Severity**: CRITICAL
**Assigned**: Architect Agent
**Files Affected**:
- `packages/cli/src/motus/config.py:30` (uses `~/.mc`)
- `packages/cli/src/motus/config_schema.py:46-47` (uses `~/.motus`)
- `packages/cli/docs/standards/userland-contract.md` (108 refs to `.motus/`)
- `packages/cli/src/motus/tracer.py:60` (uses `~/.mc`)
- 37 total references to `.mc/`, 108 to `.motus/`

**Issue**: The codebase has conflicting documentation about the directory structure:
- `config.py` uses `~/.mc` for state_dir
- `config_schema.py` uses `~/.motus` for db_path
- Documentation uses both inconsistently

**Impact**:
- User confusion about where state is stored
- Potential data loss if one path is used for writes, another for reads
- Migration complexity

**Acceptance Criteria**:
- [ ] Architectural decision: Choose ONE canonical path
- [ ] Update all code references
- [ ] Update all documentation references
- [ ] Migration guide for existing users

---

### CR-DEFECT-003: [HIGH] README Missing Installation Instructions

**Status**: OPEN
**Severity**: HIGH
**Assigned**: Documentation Agent
**File**: `packages/cli/README.md` (and root `README.md`)

**Issue**: README jumps straight to Quickstart without installation:
```bash
motus work claim TASK-001 --intent "My first task"
motus work evidence $LEASE test --passed 1
```

Problems:
1. No `pip install motusos` instruction
2. `$LEASE` is undefined - user doesn't know where this comes from
3. No prerequisite section (Python version, etc.)

**Acceptance Criteria**:
- [ ] Add "## Installation" section before Quickstart
- [ ] Add `pip install motusos` command
- [ ] Explain that `$LEASE` comes from the `claim` command output
- [ ] Add Python version requirement (3.11+)

---

### CR-DEFECT-004: [HIGH] Config File Format Inconsistency (YAML vs JSON)

**Status**: OPEN
**Severity**: HIGH
**Assigned**: Documentation Agent
**Files Affected**:
- `packages/cli/docs/cli-reference.md:1238` (says `~/.mc/config.yaml`)
- `packages/cli/src/motus/config_loader.py:7` (uses `~/.motus/config.json`)

**Issue**: Documentation says config is YAML, code uses JSON.

**Acceptance Criteria**:
- [ ] Clarify actual format (JSON per code)
- [ ] Update all documentation to match

---

### CR-DEFECT-005: [MEDIUM] SQL Table Name Interpolation

**Status**: OPEN
**Severity**: MEDIUM (low risk, not user-controlled)
**Assigned**: Security Agent
**File**: `packages/cli/src/motus/commands/db_cmd.py:78`

**Issue**:
```python
count = conn.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]
```

Table name is interpolated directly. While `name` comes from a hardcoded list (not user input), this violates the parameterized query principle.

**Acceptance Criteria**:
- [ ] Use table name quoting or validation
- [ ] Ensure no code paths allow user-controlled table names

---

### CR-DEFECT-006: [MEDIUM] Outdated Package Install Instruction

**Status**: OPEN
**Severity**: MEDIUM
**Assigned**: Documentation Agent
**File**: `packages/cli/docs/standards/specs/work-compiler/MOTUS-VISION.md:167`

**Issue**: Says `pip install motus` instead of `pip install motusos`

**Acceptance Criteria**:
- [ ] Update to `pip install motusos`

---

### CR-DEFECT-007: [MEDIUM] OTLP Ingest Bypasses Policy Gates

**Status**: OPEN
**Severity**: MEDIUM
**Assigned**: Builder Agent
**Files**:
- `packages/cli/src/motus/ingest/bridge.py:13`
- `packages/cli/src/motus/ingest/otlp.py:45` (caller)

**Issue**:
```python
# TODO: Wire to policy/runner.py run_gates() for full gate execution
```

**Impact**: Tool spans ingested via OTLP only get a simple `safety_score` check, not full gate evaluation. This is a **governance gap** - OTLP-ingested spans bypass the policy runner entirely.

**Acceptance Criteria**:
- [ ] Wire `bridge.py` to `policy/runner.py run_gates()`
- [ ] Ensure OTLP spans pass through full gate evaluation
- [ ] Add test coverage for OTLP → gate flow

---

### CR-DEFECT-008: [LOW] Checkpoint Events Missing lens_delta

**Status**: OPEN
**Severity**: LOW
**Assigned**: Builder Agent
**Files**:
- `packages/cli/src/motus/coordination/api/coordinator.py:490`
- `packages/cli/src/motus/coordination/api/types.py:235` (StatusResponse.lens_delta)

**Issue**:
```python
# TODO: Compute Lens delta
```

**Impact**: `status()` never computes `lens_delta` on checkpoint events, leaving it `None` even though `StatusResponse` supports it. Clients cannot consume delta updates on checkpoints.

**Acceptance Criteria**:
- [ ] Implement lens delta computation in `status()`
- [ ] Or document why deferred (if delta is expensive to compute)

---

## ADDITIONAL BOUNTY TARGETS

These are not defects but areas recommended for deeper testing:

### Target 1: Broad Exception Handling

**Files**:
- `packages/cli/src/motus/decisions_storage.py:61`
- `packages/cli/src/motus/orchestrator/events.py:69,112,132,142`
- `packages/cli/src/motus/orchestrator/discovery.py:60,107,117,204`
- `packages/cli/src/motus/atomic_io.py:74,77`

**Bounty**: Find cases where broad `except Exception` hides security issues or swallows important errors.

### Target 2: Path Traversal Edge Cases

**Files**:
- `packages/cli/tests/test_security.py` (existing comprehensive tests)

**Bounty**: Find path traversal vectors not covered by existing tests. Current coverage is good but edge cases (symlinks, unicode, etc.) may exist.

### Target 3: Web UI Security Headers

**Files**:
- `packages/cli/src/motus/ui/web/`

**Bounty**: Verify appropriate security headers (CSP, X-Frame-Options, X-Content-Type-Options) are set. Currently binds to localhost only (good) but headers may be missing.

### Target 4: Subprocess Environment Leakage

**Files**:
- `packages/cli/src/motus/policy/_runner_utils.py`

**Bounty**: Find environment variable leakage vectors when running gate scripts.

### Target 5: Evidence Integrity

**Files**:
- `packages/cli/src/motus/evidence/`
- Evidence bundle creation and verification

**Bounty**: Find ways to forge evidence bundles or bypass integrity checks.

---

## DEFINITION OF DONE

| Criterion | Check |
|-----------|-------|
| CR-DEFECT-001 | `python3 -m py_compile registry.py` passes |
| CR-DEFECT-002 | All path references consistent, migration tested |
| CR-DEFECT-003 | README has Install section, $LEASE explained |
| CR-DEFECT-004 | Config format documented correctly |
| CR-DEFECT-005 | No direct SQL interpolation of identifiers |
| CR-DEFECT-006 | All install instructions say `motusos` |
| All gates pass | `scripts/gates/run-all-gates.sh` exits 0 |
| Tests pass | `cd packages/cli && pytest tests/ -x` |

---

## PRIORITY ORDER

1. **CRITICAL** (blocking release):
   - CR-DEFECT-001 (FIXED)
   - CR-DEFECT-002 (path inconsistency)

2. **HIGH** (fix before v0.2.0):
   - CR-DEFECT-003 (README install)
   - CR-DEFECT-004 (config format)

3. **MEDIUM** (fix in v0.2.x):
   - CR-DEFECT-005 (SQL interpolation)
   - CR-DEFECT-006 (outdated install)
   - CR-DEFECT-007 (OTLP bypasses gates - governance gap)

4. **LOW** (backlog):
   - CR-DEFECT-008 (lens_delta not computed)

---

*Handoff created: 2026-01-06*
*Crucible agents: Gate Runner, Security Scanner, Fresh-Eyes, Proof Auditor*
*Next review: After CR-DEFECT-002 resolved*
