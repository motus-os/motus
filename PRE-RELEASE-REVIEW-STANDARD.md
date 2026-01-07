# Motus Pre-Release Review Standard

**Version**: 1.0
**Created**: 2026-01-07
**Purpose**: Comprehensive multi-phased review process for release readiness verification

---

## Current Status (fill per release)

### Phase Summary
| Phase | Status | Gate |
|-------|--------|------|
| 0. Foundation | PENDING | Prerequisites verified |
| 1. Research | PENDING | Standards documented |
| 2. README | PENDING | Install works, <2 min to understand |
| 3. Community | PENDING | Templates exist, CoC adopted |
| 4. Automation | PENDING | Workflows pass |
| 5. Technical | PENDING | Gates + tests run (record counts in artifacts) |
| 6. User Perspective | PENDING | CLI works, doctor passes |
| 7. Credibility | PENDING | All claims have evidence |
| 8. Pre-Release | PENDING | All checklists complete |

---

## Canonical References (Single Source of Truth)

- `packages/cli/docs/standards/gates.yaml` - gate definitions
- `packages/cli/docs/standards/module-registry.yaml` - module status labels
- `packages/website/standards/proof-ledger.json` - claim registry
- `scripts/gates/run-all-gates.sh` - gate execution
- `GITHUB-REVIEW-PROCESS.md` - repository presence
- `packages/website/REVIEW-PROCESS.md` - website review

## Artifact Chain (Outputs -> Constraints -> Validation)

| Phase | Output Artifact | Constraint Created | Validation (Later Phase) |
|-------|-----------------|-------------------|--------------------------|
| 0. Foundation | Gate scripts exist<br>Test suite exists | All gates must pass for release | Phase 5 gate execution |
| 1. Research | `GITHUB-REVIEW-PROCESS.md`<br>`packages/website/REVIEW-PROCESS.md` | Release must follow documented standards | Phase 5-7 audits |
| 2. README | `README.md` | Install must work in <2 minutes | Phase 6 user test |
| 3. Community | `.github/CONTRIBUTING.md`<br>Issue templates | Contributors can submit PRs | Phase 6 contribution test |
| 4. Automation | `.github/workflows/*.yml` | All CI must pass | Phase 5 technical review |
| 5. Technical | Gate execution logs<br>Test results | Zero failures before Phase 6 | Phase 8 release checklist |
| 6. User Perspective | CLI test results<br>`motus doctor` output | First-time user succeeds in <5 min | Phase 7 credibility |
| 7. Credibility | `proof-ledger.json` updated | Only verified claims ship | Phase 8 final audit |
| 8. Pre-Release | Release checklist | Ship only when all gates pass | Post-release verification |

---

## Ethos & Principles

### Core Identity

**Motus releases are evidence-backed.** The release process must reflect:
- Professional quality (gates, not gut feelings)
- Active verification (tests, not assumptions)
- Clear documentation (proof, not promises)
- Reproducible builds (anyone can verify)

### Principles

| Principle | Meaning | Anti-Pattern |
|-----------|---------|--------------|
| **Gates are law** | No release bypasses gates | "Ship it, fix it later" |
| **Tests prove behavior** | Every feature has tests | "It works on my machine" |
| **Evidence backs claims** | No claims without proof | Aspirational marketing |
| **User first** | Install must work immediately | Developer-only testing |

---

## Phase 0: Foundation Verification

**Purpose**: Ensure all release infrastructure exists before any work begins.

### Tasks

| Task | Description | Deliverable |
|------|-------------|-------------|
| 0.1 | Gate scripts exist | `scripts/gates/*.sh` |
| 0.2 | Test suite exists | `packages/cli/tests/` |
| 0.3 | CI workflows exist | `.github/workflows/` |
| 0.4 | Version set correctly | `pyproject.toml` version |
| 0.5 | CHANGELOG updated | Version entry exists |
| 0.6 | No uncommitted changes in package | `git status` clean |

### Success Criteria

- [ ] All gate scripts are executable
- [ ] Test suite has >1000 tests
- [ ] CI workflows exist for quality-gates, release
- [ ] Version number follows semver
- [ ] CHANGELOG has entry for this version
- [ ] Package directory has no uncommitted changes

### Confidence Definition

**100% confident** when: All infrastructure exists and version is set correctly.

---

## Phase 1: Research Verification

**Purpose**: Ensure release follows documented standards.

### Tasks

| Task | Description | Deliverable |
|------|-------------|-------------|
| 1.1 | GitHub review process exists | `GITHUB-REVIEW-PROCESS.md` |
| 1.2 | Website review process exists | `packages/website/REVIEW-PROCESS.md` |
| 1.3 | Gate registry exists | `packages/cli/docs/standards/gates.yaml` |
| 1.4 | Module registry exists | `packages/cli/docs/standards/module-registry.yaml` |

### Success Criteria

- [ ] All process docs exist and are current
- [ ] Gate definitions match implemented gates
- [ ] Module statuses are accurate (current/building/future)

### Confidence Definition

**100% confident** when: All process documentation exists and matches implementation.

---

## Phase 2: README Audit

**Purpose**: Ensure README enables immediate adoption.

### Tasks

| Task | Description | Deliverable |
|------|-------------|-------------|
| 2.1 | Hero section is clear | One sentence explains product |
| 2.2 | Install is one command | `pip install motusos` |
| 2.3 | Quickstart is runnable | 3 commands work |
| 2.4 | All links work | Zero broken links |
| 2.5 | Badges reflect real status | CI badge matches workflow |

### 2A: README Quality Gates

| Check | Requirement |
|-------|-------------|
| Hero | Answers "what does this do?" in <=15 words |
| Install | Single command, copy-pasteable |
| Quickstart | Commands actually run and produce expected output |
| Links | All internal and external links resolve |
| Badges | All badges reflect real status |

### Success Criteria

- [ ] README fits above fold
- [ ] Install command works on fresh machine
- [ ] Quickstart produces expected output
- [ ] Someone can understand + install in <2 minutes

### Confidence Definition

**100% confident** when: A developer unfamiliar with Motus can install and run first command in <2 minutes.

---

## Phase 3: Community Audit

**Purpose**: Ensure contribution infrastructure is ready.

### Tasks

| Task | Description | Deliverable |
|------|-------------|-------------|
| 3.1 | CONTRIBUTING.md exists | Setup + PR process documented |
| 3.2 | Issue templates exist | Bug report, feature request |
| 3.3 | PR template exists | Checklist for contributors |
| 3.4 | Code of Conduct exists | Community standards defined |
| 3.5 | CODEOWNERS exists | All paths mapped |

### Success Criteria

- [ ] CONTRIBUTING.md enables first-time contributor
- [ ] Issue templates capture required info
- [ ] PR template enforces quality
- [ ] CoC is clear with enforcement process

### Confidence Definition

**100% confident** when: A first-time contributor can submit a PR by following CONTRIBUTING.md.

---

## Phase 4: Automation Audit

**Purpose**: Ensure CI/CD pipeline is complete.

### Tasks

| Task | Description | Deliverable |
|------|-------------|-------------|
| 4.1 | Quality gates workflow exists | `.github/workflows/quality-gates.yml` |
| 4.2 | Release workflow exists | `.github/workflows/release.yml` |
| 4.3 | Dependabot configured | `.github/dependabot.yml` |
| 4.4 | Branch protection enabled | `main` requires PR + review |

### Success Criteria

- [ ] All workflows exist and pass
- [ ] Branch protection enforces CI
- [ ] Releases are automated
- [ ] Security scanning runs regularly

### Confidence Definition

**100% confident** when: All workflows pass and branch protection is enforced.

---

## Phase 5: Technical Review

**Purpose**: Execute all quality gates and verify test suite.

### Tasks

| Task | Description | Deliverable |
|------|-------------|-------------|
| 5.1 | Run all gates | `./scripts/gates/run-all-gates.sh` |
| 5.2 | Run full test suite | `pytest packages/cli/tests/` |
| 5.3 | Check coverage threshold | Coverage meets minimum |
| 5.4 | Run security scan | No high/critical vulnerabilities |
| 5.5 | Verify no flaky tests | Run tests 3x |

### 5A: Gate Requirements

| Gate | Description | Required |
|------|-------------|----------|
| GATE-PKG-001 | Package structure | Yes |
| GATE-REPO-001 | Repository hygiene | Yes |
| GATE-DB-001 | Database integrity | Yes |
| GATE-CLI-001 | CLI functionality | Yes |
| GATE-TEST-001 | Test isolation | Yes |
| GATE-SEC-002 | Security scan | Yes |
| GATE-SRC-001 | Source quality | Yes |
| All others | Per `gates.yaml` | Yes |

### 5B: Test Requirements

| Metric | Threshold |
|--------|-----------|
| Tests passing | 100% |
| Tests skipped | <10 |
| Coverage | >=80% (or justified) |
| Flaky tests | 0 |

### Success Criteria

- [ ] All gates pass (15/15)
- [ ] All tests pass (1957/1957 or current count)
- [ ] Coverage meets threshold
- [ ] No security vulnerabilities
- [ ] No flaky tests

### Confidence Definition

**100% confident** when: All gates pass, all tests pass, coverage meets threshold.

---

## Phase 6: User Perspective Test

**Purpose**: Verify the release works for first-time users.

### Tasks

| Task | Description | Deliverable |
|------|-------------|-------------|
| 6.1 | Test `motus --help` | Help displays correctly |
| 6.2 | Test `motus doctor` | All health checks pass |
| 6.3 | Test `motus list` | Command works |
| 6.4 | Test quickstart flow | 3 commands work |
| 6.5 | Check deprecation warnings | Warnings are clear |

### 6A: CLI Quality Gates

| Command | Expected |
|---------|----------|
| `motus --help` | Displays tiered command list |
| `motus doctor` | All checks pass |
| `motus list` | Shows sessions or "no sessions found" |
| `motus roadmap` | Displays roadmap items |

### 6B: Fresh Install Test

On a clean environment:

1. `pip install motusos`
2. `motus --version`
3. `motus doctor`
4. `motus --help`

**Pass**: All commands work in <5 minutes with zero errors.

### Success Criteria

- [ ] All CLI commands work
- [ ] `motus doctor` passes all checks
- [ ] Help is clear and organized
- [ ] Deprecation warnings are helpful (not confusing)
- [ ] Install + first command in <5 minutes

### Confidence Definition

**100% confident** when: A developer can install and successfully use Motus within 5 minutes.

---

## Phase 7: Credibility Review

**Purpose**: Ensure all claims are accurate and backed by evidence.

### Tasks

| Task | Description | Deliverable |
|------|-------------|-------------|
| 7.1 | Audit README claims | Claim inventory |
| 7.2 | Verify proof ledger entries | All claims registered |
| 7.3 | Check module registry | Statuses accurate |
| 7.4 | Verify evidence links | All proof links work |
| 7.5 | Remove unverified claims | Clean README |

### 7A: Claim Classification

| Status | Definition | Allowed In |
|--------|------------|------------|
| `current` | Implemented + documented + runnable | README, website |
| `building` | In development, roadmap_id required | Roadmap only |
| `future` | Concept only | Internal only |

### 7B: Evidence Requirements

Per `OUTCOME-VALIDATION.md`:

- **Outcome**: Real-world behavior change
- **Baseline**: State before change
- **Validation Method**: How to prove it
- **Evidence Artifact**: File paths to proof
- **Verification Command**: Commands to reproduce
- **Result**: Pass/Fail

### Success Criteria

- [ ] Every claim has evidence
- [ ] Every badge is accurate
- [ ] Module statuses are honest
- [ ] No aspirational statements as fact
- [ ] Proof ledger is updated

### Confidence Definition

**100% confident** when: A skeptical developer could verify every claim.

---

## Phase 8: Pre-Release Checklist

**Purpose**: Final verification before release.

### 8A: Technical Checklist

| Check | Status |
|-------|--------|
| All gates pass | |
| All tests pass | |
| Version set correctly | |
| CHANGELOG updated | |
| No uncommitted changes in package | |
| CI passes on main branch | |

### 8B: Documentation Checklist

| Check | Status |
|-------|--------|
| README current | |
| Install command works | |
| Quickstart works | |
| All links work | |
| Evidence claims have proof | |

### 8C: Release Execution

| Step | Status |
|------|--------|
| Tag created | |
| Release workflow triggered | |
| PyPI package published | |
| GitHub Release created | |
| Post-release verification | |

### 8D: Post-Release Verification

| Check | Status |
|-------|--------|
| `pip install motusos` works | |
| `motus --version` shows new version | |
| `motus doctor` passes | |
| No critical issues in first 24h | |

### Success Criteria

- [ ] All checklist items pass
- [ ] Package installs and works
- [ ] Documentation accessible
- [ ] No critical issues in first 24h

### Confidence Definition

**100% confident** when: You would be comfortable recommending Motus to a colleague right now.

---

## Phase Summary

| Phase | Purpose | Gate |
|-------|---------|------|
| 0. Foundation | Prerequisites exist | Infrastructure verified |
| 1. Research | Standards documented | Process docs exist |
| 2. README | Entry point works | Install in <2 min |
| 3. Community | Contribution enabled | Templates exist |
| 4. Automation | CI/CD complete | All workflows pass |
| 5. Technical | Code quality verified | Gates + tests pass |
| 6. User Perspective | First-time success | <5 min to first result |
| 7. Credibility | Claims verified | All claims have evidence |
| 8. Pre-Release | Ready to ship | All checklists pass |

---

## Validation Modes

### Default: Single Reviewer
- One agent runs all phases sequentially
- Record results in this document
- **Required** for patch releases

### Maker / Checker
- **Maker** executes phases and produces artifacts
- **Checker** audits strictly against this process
- **Required** for minor releases

### Parallel Validation
- Two independent full reviews
- Compare outputs before release
- **Required** for major releases

---

## When to Use This Process

### Full Process (All Phases)
- Major version release (x.0.0)
- First public release
- Post-incident release

### Standard Process (Phases 4-8)
- Minor version release (0.x.0)
- Feature additions
- Breaking changes

### Abbreviated Process (Phases 5, 6, 8)
- Patch release (0.0.x)
- Bug fixes
- Documentation updates

---

## Anti-Patterns to Avoid

| Anti-Pattern | Why It's Bad | What to Do Instead |
|--------------|--------------|-------------------|
| Skip gates | Technical debt compounds | Always run all gates |
| "Works on my machine" | User experience differs | Test fresh install |
| Ship unverified claims | Credibility destroyed | Build evidence first |
| Rush release | Quality suffers | Follow the phases |
| Manual testing only | Misses edge cases | Automated gates + manual |
| Ignore deprecation warnings | Users confused | Clear migration path |
| Skip user perspective | Jargon accumulates | Test with fresh eyes |

---

## Execution Commands

### Run All Gates
```bash
./scripts/gates/run-all-gates.sh
```

### Run Tests
```bash
PYTHONPATH=packages/cli/src python3 -m pytest packages/cli/tests/ -q
```

### Check Version
```bash
grep "version" packages/cli/pyproject.toml
```

### User Perspective Test
```bash
motus --help
motus doctor
motus list
motus roadmap
```

### Fresh Install Test
```bash
python -m venv /tmp/motus-test
source /tmp/motus-test/bin/activate
pip install motusos
motus --version
motus doctor
```

---

*This process ensures every Motus release is verified, documented, and ready for users.*
*Created 2026-01-07 as part of v0.1.1 release review.*
