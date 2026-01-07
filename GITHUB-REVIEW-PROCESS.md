# Motus GitHub Review Process

**Version**: 1.0
**Created**: 2026-01-06
**Purpose**: Comprehensive multi-phased review process for GitHub repository presence

---

## Current Status (2026-01-06)

### Phase 0: Foundation
| Item | Status | Notes |
|------|--------|-------|
| LICENSE | DONE | MCSL license |
| SECURITY.md | DONE | 48h response SLA, known limitations documented |
| CODE_OF_CONDUCT.md | DONE | Contributor Covenant |
| CODEOWNERS | DONE | All paths mapped |
| .gitignore | DONE | Excludes sensitive files |
| Branch protection | TODO | Needs manual GitHub settings |

### Phase 1: Research
| Item | Status | Notes |
|------|--------|-------|
| Research doc | DONE | `docs/github-patterns-research.md` |
| Patterns extracted | DONE | Stripe, Astro, Next.js, Rust |

### Phase 2: README
| Item | Status | Notes |
|------|--------|-------|
| README.md | DONE | Generated from `packages/cli/docs/website/messaging.yaml` |
| Quickstart | DONE | 3-command loop |
| Evidence links | DONE | `/docs/evidence` registry |

### Phase 3: Community
| Item | Status | Notes |
|------|--------|-------|
| CONTRIBUTING.md | DONE | Setup + PR process |
| Issue templates | PARTIAL | Markdown (not YAML forms) - OK for 0.X scale |
| config.yml | DONE | `blank_issues_enabled: false` |
| PR template | DONE | `.github/PULL_REQUEST_TEMPLATE.md` |
| E-easy labels | TODO | Need to curate 3-5 good first issues |

### Phase 4: Automation
| Item | Status | Notes |
|------|--------|-------|
| CI workflows | DONE | Multiple workflows in `.github/workflows/` |
| Dependabot | DONE | `.github/dependabot.yml` |
| Installation testing | TODO | Per Stripe pattern |

### Next Actions
1. Enable branch protection on GitHub (manual)
2. Create 3-5 `E-easy` labeled issues
3. Add installation testing workflow

---

## Canonical References (Single Source of Truth)

- `README.md` - primary entry point, installation, value proposition
- `CONTRIBUTING.md` - contribution guidelines
- `CODE_OF_CONDUCT.md` - community standards
- `.github/` - templates, workflows, community health files
- `docs/quality/MANUAL-GITHUB-SETUP.md` - required GitHub UI settings
- `docs/` - technical documentation
- `CHANGELOG.md` - release history

## Artifact Chain (Outputs → Constraints → Validation)

| Phase | Output Artifact | Constraint Created | Validation (Later Phase) |
|-------|-----------------|-------------------|--------------------------|
| 0. Foundation | `.github/CODEOWNERS`<br>`LICENSE`<br>`SECURITY.md` | All PRs require owner review; license terms fixed; security policy defined | Phase 5 CI checks; Phase 7 security audit |
| 1. Research | `docs/github-patterns-research.md` | README structure must follow best practices; badges must match research | Phase 2 README review; Phase 6 user test |
| 2. README | `README.md`<br>`packages/website/src/pages/get-started.astro`<br>`packages/website/src/data/tutorial.yaml` | All claims must be provable; install command must work | Phase 5 CI; Phase 6 user test; Phase 7 claim audit |
| 3. Community | `CONTRIBUTING.md`<br>`CODE_OF_CONDUCT.md`<br>`.github/ISSUE_TEMPLATE/`<br>`.github/PULL_REQUEST_TEMPLATE.md` | All contributions follow template; CoC enforced | Phase 5 template validation |
| 4. Automation | `.github/workflows/`<br>`scripts/` | All PRs must pass CI; releases automated | Phase 5 CI audit |
| 5. Technical Review | `artifacts/phase-5-github-audit.md` | All checks must pass before Phase 6 | Phase 8 release checklist |
| 6. User Perspective | `artifacts/phase-6-github-tests.md` | First-time user can install + run in <5 min | Phase 7 claim verification |
| 7. Credibility | `artifacts/phase-7-github-audit.md`<br>`packages/cli/docs/website/proof-ledger.yaml`<br>`packages/website/src/data/proof-ledger.json` | Only verified claims in README | Phase 8 release checklist |
| 8. Pre-Release | `docs/quality/release-checklist.md` | Release only when all gates pass | Post-release verification |

---

## Ethos & Positioning

### Core Identity

**Motus is developer infrastructure.** The GitHub presence must reflect:
- Professional quality (not a side project)
- Active maintenance (not abandoned)
- Clear documentation (not "read the code")
- Welcoming community (not hostile gatekeeping)

### Principles

| Principle | Meaning | Anti-Pattern |
|-----------|---------|--------------|
| **README is the product** | First impression determines adoption | Wall of text, missing examples, broken install |
| **Docs that work** | Every code example must run | Outdated snippets, missing dependencies |
| **Badges that mean something** | Only show real status | Fake badges, broken CI showing green |
| **Responsive maintenance** | Issues get replies within 48h | Stale issues, unanswered questions |

---

## Phase 0: Foundation Verification

**Purpose**: Ensure all repository prerequisites exist.

### Tasks

| Task | Description | Deliverable |
|------|-------------|-------------|
| 0.1 | License exists and is appropriate | `LICENSE` (MIT/Apache 2.0) |
| 0.2 | Security policy exists | `SECURITY.md` |
| 0.3 | Code owners defined | `.github/CODEOWNERS` |
| 0.4 | Branch protection enabled | `main` protected |
| 0.5 | Repository settings configured | Description, topics, website URL |
| 0.6 | Sensitive files excluded | `.gitignore` complete |
| 0.7 | No secrets in history | `git log` audit |

### Success Criteria

- [ ] LICENSE file exists with correct license
- [ ] SECURITY.md exists with disclosure policy
- [ ] CODEOWNERS maps all critical paths
- [ ] `main` branch requires PR + review
- [ ] Repository has description, topics, and homepage URL
- [ ] No API keys, tokens, or credentials in git history

### Confidence Definition

**100% confident** when: A security auditor would find no issues with repository configuration.

---

## Phase 1: Research

**Purpose**: Study world-class open source repos before writing README.

### 1A: Repository Research

Study these repositories (research completed 2026-01-06, see `docs/github-patterns-research.md`):

| Repository | Why | Key Patterns Extracted |
|------------|-----|------------------------|
| **Stripe CLI** | Gold standard CLI | Tests installation hourly, multi-platform configs, VirusTotal integration |
| **Astro** | Modern tooling | YAML issue forms, changesets + OIDC, champion-driven RFCs, disable blank issues |
| **Vercel/Next.js** | Scale patterns | 81 labels, matrix testing, aggregation jobs, auto-triage via regex |
| **Rust** | Community excellence | Graduated CoC enforcement, 24/48h security SLA, E-easy/E-mentor labels, RFC + FCP process |

### 1B: Pattern Extraction

Document patterns for:
- README structure (hero, install, usage, contributing)
- Badge placement and meaning
- Code example presentation
- Issue/PR template design
- Release notes format

### Tasks

| Task | Description | Deliverable |
|------|-------------|-------------|
| 1.1 | Research 5+ top repos | Pattern notes |
| 1.2 | Extract README patterns | README template |
| 1.3 | Extract template patterns | Issue/PR templates |
| 1.4 | Extract CI patterns | Workflow templates |

### Success Criteria

- [ ] 5+ repos researched with documented insights
- [ ] README structure defined based on research
- [ ] Template patterns documented
- [ ] No decisions made without reference to research

---

## Phase 2: README

**Purpose**: Create a README that converts visitors to users.

### 2A: README Structure

| Section | Purpose | Requirements |
|---------|---------|--------------|
| Hero | What is this? | One sentence, no jargon |
| Badges | Trust signals | Only real, meaningful badges |
| Install | Get started | One command, works immediately |
| Quick Example | Show value | Runnable in <30 seconds |
| Features | Why use this? | Benefits, not features list |
| Documentation | Learn more | Links to full docs |
| Contributing | How to help | Link to CONTRIBUTING.md |
| License | Legal | Link to LICENSE |

### 2B: README Quality Gates

| Check | Requirement |
|-------|-------------|
| Hero | ≤15 words, answers "what does this do?" |
| Install | Single command, copy-pasteable |
| Example | Actually runs, produces output shown |
| Links | All links work (internal and external) |
| Badges | All badges reflect real status |
| Grammar | No typos, consistent voice |

### 2C: What NOT to Include in README

- Changelog (use CHANGELOG.md)
- Full API reference (use docs/)
- Development setup (use CONTRIBUTING.md)
- Wall of badges
- GIFs that don't add value

### Tasks

| Task | Description | Deliverable |
|------|-------------|-------------|
| 2.1 | Write hero section | One sentence |
| 2.2 | Define badges | Badge list with sources |
| 2.3 | Write install section | One-liner that works |
| 2.4 | Write quick example | Runnable code |
| 2.5 | Write features | 3-5 key benefits |
| 2.6 | Add links | Docs, contributing, license |
| 2.7 | Test all commands | All run successfully |

### Success Criteria

- [ ] README fits on one screen (above fold)
- [ ] Install command works on fresh machine
- [ ] Example produces expected output
- [ ] All links resolve
- [ ] Someone can understand + install in <2 minutes

---

## Phase 3: Community

**Purpose**: Enable contributions and maintain healthy community.

### 3A: Contributing Guide

| Section | Content |
|---------|---------|
| Welcome | Thank contributors, set expectations |
| Prerequisites | Exact versions (from Astro: `Node.js: ^>=18.20.8`) |
| Development Setup | Step-by-step, include git config (from Astro) |
| Code Standards | Style guide, linting, testing |
| PR Process | How to submit, what to expect |
| Issue Guidelines | Bug reports vs features |
| Architectural Context | Folder structure by execution context (from Astro) |

**Key Pattern (Astro)**: Separate contributor docs from maintainer docs. Include architectural context, not just setup commands.

### 3B: Issue Templates

**Use YAML-based forms** (from Astro/Next.js), not markdown templates:

| Template | Purpose | Required Fields |
|----------|---------|-----------------|
| Bug Report | Reproducible issues | Version, OS, steps, expected, actual, **reproduction link** |
| Feature Request | New functionality | Problem, solution, alternatives |
| Question | Support | What you tried, what you expected |

**Critical Pattern (Astro)**: Auto-close issues without reproduction. Add warning:
> "Issues without reproduction will be closed after 3 days."

**Disable Blank Issues** via `.github/ISSUE_TEMPLATE/config.yml`:
```yaml
blank_issues_enabled: false
contact_links:
  - name: Discord Support
    url: https://discord.gg/motus
    about: For questions and support (issues are for bugs only)
```

### 3C: PR Template

```markdown
## Description
[What does this PR do?]

## Type
- [ ] Bug fix
- [ ] Feature
- [ ] Documentation
- [ ] Refactor

## Checklist
- [ ] Tests pass
- [ ] Docs updated
- [ ] CHANGELOG updated
```

### 3D: Code of Conduct

Adopt Contributor Covenant or equivalent. Must include:
- Expected behavior
- Unacceptable behavior
- Enforcement process
- Contact information

**Graduated Enforcement (from Rust)**:
1. Warning for violations
2. Temporary removal if warnings ignored
3. Ban for continued violations
4. Possible unban with genuine apology (restorative justice)

### 3E: Contributor Onboarding Labels (from Rust)

| Label | Purpose |
|-------|---------|
| `E-easy` | Good for newcomers, clear scope |
| `E-mentor` | Maintainer will guide contributor |
| `A-*` | Area labels (A-cli, A-api, A-docs) |
| `C-*` | Category (C-bug, C-enhancement) |

**Key Pattern**: Label 3-5 issues as `E-easy` before announcing the project. Curate actively - don't just label everything.

### Tasks

| Task | Description | Deliverable |
|------|-------------|-------------|
| 3.1 | Write CONTRIBUTING.md | Complete guide with architectural context |
| 3.2 | Create YAML issue templates | 3 templates (bug, feature, question) |
| 3.3 | Create issue config | `config.yml` disabling blank issues |
| 3.4 | Create PR template | 1 template with changeset reminder |
| 3.5 | Adopt Code of Conduct | CODE_OF_CONDUCT.md with enforcement |
| 3.6 | Create onboarding labels | E-easy, E-mentor, A-*, C-* |
| 3.7 | Curate good first issues | 3-5 labeled before launch |
| 3.8 | Test contribution flow | End-to-end test |

### Success Criteria

- [ ] CONTRIBUTING.md enables first-time contributor
- [ ] YAML issue forms capture required info
- [ ] Blank issues disabled, support redirected
- [ ] PR template enforces quality
- [ ] CoC is clear with graduated enforcement
- [ ] 3+ issues labeled `E-easy` before launch

---

## Phase 4: Automation

**Purpose**: Ensure consistent quality through CI/CD.

### 4A: Required Workflows

| Workflow | Trigger | Purpose |
|----------|---------|---------|
| CI | PR, push to main | Tests, lint, type check |
| Release | Tag push | Build, publish, changelog |
| Security | Schedule, PR | Dependency audit |
| Docs | Push to main | Deploy documentation |

### 4B: CI Requirements

| Check | Requirement |
|-------|-------------|
| Tests | All tests pass |
| Coverage | ≥80% (or justified lower) |
| Lint | Zero warnings |
| Types | Zero errors |
| Build | Succeeds |
| Security | No high/critical vulnerabilities |
| **Installation** | Fresh `pip install` works (from Stripe) |

**Critical Pattern (Stripe CLI)**: Test the installation experience, not just the code.
```yaml
# install-test.yml - Run hourly + on release
- name: Test pip install
  run: |
    python -m venv /tmp/test-env
    source /tmp/test-env/bin/activate
    pip install motusos
    motus --version
```

### 4C: Release Automation

| Step | Automation |
|------|------------|
| Version bump | Semantic versioning |
| Changelog | Generated from commits |
| Build | Automated |
| Publish | Automated to PyPI/npm |
| GitHub Release | Auto-created with notes |

### Tasks

| Task | Description | Deliverable |
|------|-------------|-------------|
| 4.1 | Create CI workflow | `.github/workflows/ci.yml` |
| 4.2 | Create release workflow | `.github/workflows/release.yml` |
| 4.3 | Create security workflow | `.github/workflows/security.yml` |
| 4.4 | Configure branch protection | Settings configured |
| 4.5 | Test all workflows | All pass |

### Success Criteria

- [ ] All workflows exist and pass
- [ ] Branch protection enforces CI
- [ ] Releases are fully automated
- [ ] Security scanning runs regularly

---

## Phase 5: Technical Review

**Purpose**: Verify all automation and docs work correctly.

### 5A: Documentation Audit

| Check | Method |
|-------|--------|
| All code examples run | Execute each one |
| All links work | Link checker |
| No outdated content | Manual review |
| Version numbers correct | Grep and verify |

### 5B: CI/CD Audit

| Check | Method |
|-------|--------|
| All workflows pass | GitHub Actions status |
| Coverage meets threshold | Coverage report |
| No flaky tests | Run 3x |
| Release works | Test release to test PyPI |

### 5C: Security Audit

| Check | Method |
|-------|--------|
| No secrets in repo | `git log` search, trufflehog |
| Dependencies clean | `pip-audit`, `npm audit` |
| SECURITY.md accurate | Manual review |
| Branch protection on | Settings check |

**Security SLA (from Rust)**:
- 24-hour acknowledgment
- 48-hour detailed response
- 72-hour pre-notification to distributions before public disclosure

**5-Step Coordinated Disclosure (Rust pattern)**:
1. Assignment: Primary handler designated
2. Confirmation: Problem verified
3. Audit: Similar issues searched
4. Fix: Private patches prepared, CVE reserved
5. Disclosure: Blog post + code push within 1 hour

### Tasks

| Task | Description | Deliverable |
|------|-------------|-------------|
| 5.1 | Run all code examples | Pass/fail list |
| 5.2 | Check all links | Zero broken |
| 5.3 | Verify all workflows | All green |
| 5.4 | Run security scan | Zero high/critical |
| 5.5 | Fix all issues | Zero remaining |

### Success Criteria

- [ ] All examples run successfully
- [ ] Zero broken links
- [ ] All CI workflows pass
- [ ] Zero security vulnerabilities
- [ ] Coverage meets threshold

---

## Phase 6: User Perspective Review

**Purpose**: Verify the repo works for first-time users.

### 6A: Fresh Install Test

On a clean machine (or container):

1. Clone the repo
2. Follow README install instructions
3. Run the quick example
4. Time the entire process

**Pass**: Complete in <5 minutes with zero errors.

### 6B: First Contribution Test

1. Fork the repo
2. Follow CONTRIBUTING.md setup
3. Make a trivial change
4. Submit a PR
5. Observe the CI feedback

**Pass**: Clear feedback at every step.

### 6C: Issue Submission Test

1. Create a bug report using template
2. Create a feature request using template
3. Verify templates guide user effectively

**Pass**: Templates capture all needed info.

### Tasks

| Task | Description | Deliverable |
|------|-------------|-------------|
| 6.1 | Fresh install test (3 environments) | Test results |
| 6.2 | First contribution test | Test results |
| 6.3 | Issue submission test | Test results |
| 6.4 | Fix any friction points | Zero friction |

### Success Criteria

- [ ] Install works on macOS, Linux, Windows
- [ ] Contribution flow is clear
- [ ] Issue templates are helpful
- [ ] <5 minute time to first success

---

## Phase 7: Credibility Review

**Purpose**: Ensure all claims are accurate.

### 7A: README Claim Audit

For every claim in README:

| Claim Type | Requirement |
|------------|-------------|
| Performance | Benchmark with methodology |
| Compatibility | Test matrix with results |
| "Works with X" | Tested integration |
| Statistics | Source and date |

### 7B: Badge Audit

| Badge | Requirement |
|-------|-------------|
| Build status | Actually reflects CI |
| Coverage | Matches real coverage |
| Version | Matches latest release |
| License | Matches LICENSE file |

### 7C: Proof Requirements

Same standards as website: claims must be in `packages/cli/docs/website/proof-ledger.yaml` (source) and synced to
`packages/website/src/data/proof-ledger.json` with status `current`.

### Tasks

| Task | Description | Deliverable |
|------|-------------|-------------|
| 7.1 | List all README claims | Claim inventory |
| 7.2 | Verify each claim | Evidence per claim |
| 7.3 | Audit all badges | Badge verification |
| 7.4 | Update proof ledger | Claims registered |
| 7.5 | Remove unverified claims | Clean README |

### Success Criteria

- [ ] Every claim has evidence
- [ ] Every badge is accurate
- [ ] No aspirational statements presented as fact
- [ ] Proof ledger updated

---

## Phase 8: Pre-Release

**Purpose**: Final verification before public release.

### 8A: Release Checklist

| Check | Status |
|-------|--------|
| All tests pass | |
| All docs current | |
| CHANGELOG updated | |
| Version bumped | |
| No TODO/FIXME in release | |
| All links work | |
| Security scan clean | |
| License headers present | |

### 8B: Announcement Checklist

| Check | Status |
|-------|--------|
| Release notes written | |
| Social post drafted | |
| Documentation deployed | |
| PyPI/npm package published | |
| GitHub Release created | |

### 8C: Post-Release Verification

| Check | Status |
|-------|--------|
| `pip install motusos` works | |
| Quick start example works | |
| Docs are accessible | |
| No immediate critical issues | |

### Tasks

| Task | Description | Deliverable |
|------|-------------|-------------|
| 8.1 | Complete release checklist | All checks pass |
| 8.2 | Create release | GitHub Release |
| 8.3 | Publish package | PyPI/npm |
| 8.4 | Verify installation | Works on clean machine |
| 8.5 | Monitor for issues | 24h watch |

### Success Criteria

- [ ] All checklist items pass
- [ ] Package installs and works
- [ ] Documentation accessible
- [ ] No critical issues in first 24h

---

## Phase Summary

| Phase | Purpose | Gate |
|-------|---------|------|
| 0. Foundation | Repository configured | Security + settings verified |
| 1. Research | Patterns identified | Research documented |
| 2. README | Entry point created | Install works, <2 min to understand |
| 3. Community | Contribution enabled | Templates exist, CoC adopted |
| 4. Automation | Quality enforced | All workflows pass |
| 5. Technical | Everything works | Zero errors/warnings |
| 6. User Perspective | First-time success | <5 min to first result |
| 7. Credibility | Claims verified | All claims have evidence |
| 8. Pre-Release | Ready to ship | All checklists pass |

---

## Validation Modes

### Default: Maker / Checker
- **Maker** applies phases and produces artifacts.
- **Checker** audits strictly against this process.
- **Required** for README changes and releases.

### High Stakes: Parallel Validation
- Two independent reviews for major releases.
- Compare outputs before merge.

---

## When to Use This Process

### Full Process (All Phases)
- Initial public release
- Major version release
- Repository restructure

### Abbreviated (Phases 5-8)
- Minor releases
- Documentation updates
- Dependency updates

### Skip to Phase 7
- README claim changes
- Badge updates

---

## Anti-Patterns to Avoid

| Anti-Pattern | Why It's Bad | What to Do Instead |
|--------------|--------------|-------------------|
| README as changelog | Buries the value prop | Use CHANGELOG.md |
| Fake badges | Destroys trust | Only show real status |
| Outdated examples | Breaks first experience | Test examples in CI |
| Ignored issues | Signals abandonment | Respond within 48h |
| Manual releases | Error-prone | Automate everything |
| Missing CoC | Unwelcoming | Adopt standard CoC |
| Secrets in history | Security risk | Use git-filter-repo to remove |
| Blank issues allowed | Unstructured reports | Use YAML forms, disable blank |
| No reproduction required | Can't debug | Auto-close without repro |
| No installation tests | "Works for me" | Test fresh install in CI |

---

## Scale-Appropriate Adoption (from Research)

**What NOT to copy blindly** (from Next.js analysis):
- Don't create 34 workflows if you have 3 contributors
- Don't need 81 labels if you get 10 issues/month
- Don't need daily canary releases if you ship monthly

**Motus Priority Order**:

| Priority | Pattern | Source | Effort |
|----------|---------|--------|--------|
| Week 1 | YAML issue templates + disable blank | Astro | Low |
| Week 1 | SECURITY.md with 48h SLA | Rust | Low |
| Week 1 | E-easy labels (3-5 issues) | Rust | Low |
| Month 1 | Installation testing in CI | Stripe | Medium |
| Month 1 | Changesets for releases | Astro | Medium |
| Month 1 | Auto-labeling by file path | Astro | Medium |
| Quarter 1 | Lightweight RFC process | Rust | Medium |
| Quarter 1 | Preview releases via PR label | Astro | Low |

---

## Research Artifacts

Full research documentation: `docs/github-patterns-research.md`

Sources studied:
- Stripe CLI (stripe/stripe-cli)
- Astro (withastro/astro)
- Next.js (vercel/next.js)
- Rust (rust-lang/rust, rust-lang/rfcs)

---

*This process ensures the Motus GitHub presence meets the same quality standards as the product itself.*
*Research conducted 2026-01-06 by Opus with Sonnet sub-agents.*
