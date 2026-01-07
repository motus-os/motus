# GitHub Best Practices Research

**Date**: 2026-01-06
**Sources**: Stripe CLI, Astro, Next.js, Rust
**Purpose**: Ground GITHUB-REVIEW-PROCESS.md in world-class precedent

---

## Executive Summary

| Pattern | Source | Adoption Priority |
|---------|--------|-------------------|
| README as router, not manual | Astro | High |
| YAML issue forms with auto-close | Astro, Next.js | High |
| Disable blank issues | Astro, Next.js | High |
| Test installation, not just code | Stripe | High |
| Changesets + OIDC for releases | Astro | Medium |
| Champion-driven RFCs | Astro, Rust | Medium |
| Graduated CoC enforcement | Rust | High |
| Security response SLAs | Rust | High |
| Auto-label by file path | Astro | Medium |
| Preview releases via PR labels | Astro | Low |

---

## 1. README Patterns

### Stripe CLI
- **Visual-first**: Animated GIF demo near top
- **Multi-platform install**: Homebrew, apt, scoop, Docker, manual
- **Capability-focused**: Frame as user goals, not features
- **Link externally for depth**: Keep README concise

### Astro
- **Ultra-concise opening**: One sentence value proposition
- **Three-tier install**: Recommended, manual, browser-based
- **README as router**: Links to docs, doesn't duplicate
- **Transparent monorepo org**: Lists all packages with categories

### Next.js
- **Gateway document**: ~100 lines, clear hierarchy
- **Trust signals upfront**: Badges for version, license, community
- **Multiple user pathways**: Learners → docs, contributors → issues
- **Delegates depth**: External documentation handles details

### Key Insight
> "Write your README as a '30-second decision maker' - help visitors decide if this is the right tool."

---

## 2. Issue & PR Templates

### Astro (Best-in-Class)
- **YAML-based forms** with structured fields
- **Auto-close warning**: Issues without reproduction closed automatically
- **Disables blank issues**: Forces template use
- **4 alternative channels**: Discord, docs repo, roadmap, chat
- **PR template**: Changes, Testing, Docs sections + changeset reminder

### Next.js
- **5 mandatory fields**: Reproduction, steps, expected/actual, environment, area
- **Validates reproduction links**: Approved hosts only (GitHub, CodeSandbox)
- **Auto-triage**: Extracts labels from descriptions via regex
- **Stale policy**: 30 days → stale → auto-close; 14 days → lock

### Rust
- **12 specialized templates**: ICE, regression, diagnostics, tracking
- **Auto-labels on creation**: C-bug, etc.
- **Difficulty + area labels**: E-easy, E-mentor, A-async-await

### Key Insight
> "Disable blank issues to enforce structure. Route support to Discord, keep issues for actionable bugs."

---

## 3. CI/CD Patterns

### Stripe CLI (Unique)
- **Tests installation experience**: 6 package managers tested hourly
- **Platform-specific configs**: Separate GoReleaser for mac/linux/windows
- **VirusTotal integration**: Security scanning for Windows binaries
- **Multi-arch Docker**: AMD64 + ARM64 with unified manifest

### Astro
- **Changesets**: Auto-changelog, no auto-commit, patch bumps for internal deps
- **OIDC for npm**: No tokens stored - modern security
- **Preview releases**: `pr preview` label triggers pre-merge publish
- **Discord notifications**: Auto-notify community on publish

### Next.js
- **Dependency-based DAG**: Foundation jobs feed downstream
- **Matrix testing**: Node [20,22] × React ['', '18.3.1'] × Groups [1-10]
- **fail-fast: false**: See all failures, not just first
- **Aggregation jobs**: Final `tests-pass` consolidates results

### Key Insight
> "Test your installation process, not just your code. Stripe's hourly validation catches package manager breakage before users report it."

---

## 4. Release Process

### Astro
- **Changesets with GitHub changelog**: Auto-generates from PR titles
- **Multi-branch support**: main, 1-legacy through 4-legacy
- **VS Code extension parallel publishing**: Marketplace + OpenVSX
- **OIDC authentication**: No npm tokens required

### Rust
- **6-week predictable cadence**: Stable, Beta, Nightly channels
- **75-90 minute release duration**: Highly automated
- **Coordinated communication**: Blog post after release completes
- **PR labeling during development**: `relnotes`, `relnotes-perf` for tracking

### Next.js
- **Canary releases**: Daily from canary branch
- **Breaking change marking**: `!` in commit messages
- **Upgrade guides per version**: v13→v14, v14→v15
- **Codemods for migrations**: Automated transformations

### Key Insight
> "Separate the mechanical release (code deployment) from communication (blog post, social). Have a dedicated person for comms."

---

## 5. Security Policies

### Rust (Gold Standard)
- **24-hour acknowledgment, 48-hour detailed response**
- **5-step coordinated disclosure**: Assignment → Confirmation → Audit → Fix → Disclosure
- **72-hour pre-notification**: Distributions notified before public
- **Private security repo**: Coordinate fixes before disclosure
- **Clear scope**: IN vs OUT of scope defined

### Stripe
- **Vulnerability Disclosure Program**: Formal bounty program
- **2 public advisories**: Transparent about past issues
- **GitHub Advisory integration**: Database linkage

### Key Insight
> "Speed matters more than perfection. Commit to 24/48-hour responses, not immediate fixes. This builds trust without creating impossible obligations."

---

## 6. Governance & Community

### Rust (Best-in-Class CoC)
- **Specific behavioral standards**: Not platitudes
- **Graduated enforcement**: Warning → Temporary removal → Ban → Possible unban
- **Higher moderator standards**: Leadership held accountable
- **Shared responsibility**: Members look out for each other

### Astro
- **4-tier contributor system**: Contributor → Maintainer → Core → Steward
- **70%+ majority for decisions**: 3-day voting period
- **Steward veto with disclosure**: Single authority with transparency
- **Contributor celebration workflow**: Auto-post to Discord with emojis

### Rust RFC Process
- **Pre-RFC on Zulip**: Gather feedback before formal submission
- **10-day Final Comment Period**: Requires full subteam sign-off
- **Decouples approval from implementation**: "Yes, eventually" possible
- **RFC template**: Summary, Motivation, Guide-level, Reference-level, Drawbacks, Alternatives, Prior art

### Key Insight
> "Create a lightweight RFC template (Problem, Proposal, Alternatives, Unresolved). Require it only for breaking changes or major features."

---

## 7. Onboarding Patterns

### Rust
- **E-easy and E-mentor labels**: Difficulty + mentorship flags
- **"For most PRs, no special procedures"**: Explicit low barrier
- **Escalation paths**: Triage Working Group after 2 weeks
- **Explicit permission to ask**: "When in doubt, ask on Zulip"

### Astro
- **Champion model**: Community members can drive features end-to-end
- **Parallel prototyping**: "Develop in parallel with RFC review"
- **No blocking**: Maintainers expected to provide timely feedback

### Stripe
- **Good first issues curated**: Clear scope, isolated scenarios
- **3 current examples**: Enhancement, enhancement, bug fix mix
- **Wiki for extensive guides**: Not cluttering repository

### Key Insight
> "Label 3-5 issues as 'good first issue' before announcing the project. Respond to first-time contributors within 24 hours."

---

## Anti-Patterns Observed

### Stripe Gaps
- **Release notes too sparse**: Even technical users need categorization
- **Issue triage overwhelm**: 189 open, minimal responses
- **Missing CHANGELOG.md**: Relies solely on GitHub releases
- **Single Go version in CI**: Should test multiple versions

### Next.js Gaps
- **81 labels**: Too many for smaller projects
- **34 workflows**: Overkill for most

### Key Insight
> "Don't create 34 workflows if you have 3 contributors. Don't need 81 labels if you get 10 issues/month."

---

## Motus-Specific Recommendations

### High Priority (Week 1)
1. Create YAML issue templates (bug, feature, question)
2. Disable blank issues, redirect support to Discord/Discussions
3. Add SECURITY.md with 48-hour response commitment
4. Create 10-15 essential labels (type, status, area, priority)
5. Set up auto-labeling by file path

### Medium Priority (Month 1)
6. Implement Changesets for release automation
7. Create lightweight RFC template for breaking changes
8. Add installation testing to CI (pip install from fresh env)
9. Set up stale issue automation (60 days → stale → close)
10. Create CODEOWNERS for review routing

### Lower Priority (Quarter 1)
11. Preview releases via PR labels
12. Contributor celebration workflow
13. Multi-platform CI matrix
14. Formal governance documentation

---

*Research conducted 2026-01-06 by Opus with Sonnet sub-agents*
