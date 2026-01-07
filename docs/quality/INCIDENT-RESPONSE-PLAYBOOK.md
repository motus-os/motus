# Motus Incident Response Playbook

This playbook defines procedures for responding to post-release incidents, including rollback decisions, user communication, and postmortem processes.

**Owner:** CODEOWNERS
**Last Updated:** 2026-01-07
**Version:** 1.0.0

---

## Table of Contents

1. [Incident Severity Levels](#incident-severity-levels)
2. [Rollback Decision Framework](#rollback-decision-framework)
3. [Rollback Mechanics](#rollback-mechanics)
4. [Incident Response Procedures](#incident-response-procedures)
5. [Communication Templates](#communication-templates)
6. [Postmortem Process](#postmortem-process)
7. [Prevention and Process Updates](#prevention-and-process-updates)

---

## Incident Severity Levels

### SEV-1: Critical (Rollback Required)

**Definition:** Issues that require immediate rollback or hotfix.

| Condition | Example | Response Time |
|-----------|---------|---------------|
| Data loss or corruption | Database migrations destroy user data | Immediate |
| Security vulnerability | Remote code execution, credential exposure | Immediate |
| Complete functionality failure | CLI crashes on every invocation | < 1 hour |
| Dependency chain break | Required dependency yanked from PyPI | < 1 hour |

**Authorization:** Any team member can initiate SEV-1 response. Post-action review required.

### SEV-2: High (Hotfix Required, No Rollback)

**Definition:** Significant issues that need urgent fix but don't warrant rollback.

| Condition | Example | Response Time |
|-----------|---------|---------------|
| Major feature broken | `motus claim` fails in specific scenarios | < 4 hours |
| Performance regression > 10x | Operations taking 10+ seconds vs 1 second | < 4 hours |
| Incorrect data written | Wrong timestamps in audit log | < 8 hours |

**Authorization:** Maintainer review required before action.

### SEV-3: Medium (Normal Fix Cycle)

**Definition:** Issues that affect users but have workarounds.

| Condition | Example | Response Time |
|-----------|---------|---------------|
| Edge case failures | Unicode handling issues | Next release |
| Minor data issues | Extra whitespace in output | Next release |
| Documentation mismatch | CLI help text incorrect | Next release |

**Authorization:** Standard PR review process.

### SEV-4: Low (Backlog)

**Definition:** Cosmetic or enhancement requests.

| Condition | Example | Response Time |
|-----------|---------|---------------|
| UI improvements | Color scheme tweaks | Best effort |
| Performance < 2x regression | Slightly slower but acceptable | Best effort |
| Feature requests | Nice-to-have functionality | Roadmap review |

---

## Rollback Decision Framework

### Decision Tree

```
Is the issue confirmed reproducible?
├── No → Gather more data (see Triage Checklist)
└── Yes → Continue

Does the issue affect data integrity?
├── Yes → SEV-1: Initiate rollback immediately
└── No → Continue

Does the issue expose security vulnerability?
├── Yes → SEV-1: Initiate rollback immediately
└── No → Continue

Does the issue prevent core functionality?
├── Yes → Is there a workaround?
│   ├── No → SEV-1: Initiate rollback
│   └── Yes → SEV-2: Prepare hotfix
└── No → Continue

What percentage of users are affected?
├── > 50% → SEV-2: Prepare hotfix urgently
├── 10-50% → SEV-2/3: Hotfix or next release
└── < 10% → SEV-3/4: Normal process
```

### The 30-Minute Rule

For SEV-1 issues:

1. **0-5 minutes:** Confirm the issue exists
2. **5-15 minutes:** Attempt quick fix if obvious
3. **15-30 minutes:** If not fixed, initiate rollback

Do not spend more than 30 minutes trying to fix a SEV-1 issue before rolling back. Users with broken software cannot wait.

### Who Can Authorize Rollback

| Severity | Authorization Required |
|----------|----------------------|
| SEV-1 | Any team member (document decision) |
| SEV-2 | Maintainer approval |
| SEV-3+ | Not applicable (no rollback) |

For SEV-1, the person discovering the issue is authorized to act. Document the decision in the incident issue.

---

## Rollback Mechanics

### Understanding PyPI Rollback Options

PyPI does not allow true "rollbacks" in the traditional sense. You have two options:

#### Option A: Yank (Preferred for Security Issues)

```bash
# Yank makes version installable only by pinned requirement
pip install twine
twine yank motusos -v 0.1.1
```

**When to Yank:**
- Security vulnerabilities
- Malicious code discovered
- Dependency that was yanked

**Effect:**
- `pip install motusos` gets previous version
- `pip install motusos==0.1.1` still works (for debugging)
- Users with pinned requirements can still install

#### Option B: Publish Patch Version (Preferred for Bugs)

```bash
# Publish 0.1.2 that reverts problematic changes
git revert <commit>  # Revert the breaking change
# Bump version to 0.1.2 in pyproject.toml
# Follow normal release process
```

**When to Patch:**
- Functional bugs
- Performance regressions
- Data format issues

**Effect:**
- `pip install motusos --upgrade` gets fixed version
- Clear version history
- Proper changelog entry

### Step-by-Step Rollback Procedures

#### Procedure A: PyPI Yank (Security Issues)

```bash
# 1. Document the decision
gh issue create --title "SEV-1: Yanking v0.1.1 - [REASON]" \
  --body "$(cat <<'EOF'
## Incident Summary
- **Version:** 0.1.1
- **Issue:** [Brief description]
- **Impact:** [Who is affected]
- **Decision:** Yank from PyPI

## Timeline
- [TIME] Issue discovered
- [TIME] Confirmed reproducible
- [TIME] Decision to yank
- [TIME] Yank executed

## Next Steps
- [ ] Post yank announcement
- [ ] Prepare hotfix
- [ ] Schedule postmortem
EOF
)"

# 2. Yank the release
pip install twine
twine yank motusos -v 0.1.1

# 3. Verify yank
curl -s "https://pypi.org/pypi/motusos/json" | python3 -c "
import json, sys
data = json.load(sys.stdin)
version = '0.1.1'
if version in data.get('releases', {}):
    release = data['releases'][version]
    yanked = all(f.get('yanked', False) for f in release)
    print(f'{version}: {\"YANKED\" if yanked else \"AVAILABLE\"}')"

# 4. Post announcement (see Communication Templates)
```

#### Procedure B: Emergency Patch Release

```bash
# 1. Create hotfix branch from the previous stable tag
git checkout v0.1.0
git checkout -b hotfix/0.1.2

# 2. Cherry-pick or revert
git revert <problematic-commit>  # If reverting
# OR
git cherry-pick <fix-commit>     # If there's a fix

# 3. Bump version
# Edit packages/cli/pyproject.toml: version = "0.1.2"

# 4. Update CHANGELOG
cat >> CHANGELOG_ENTRY.md << 'EOF'
## [0.1.2] - 2026-01-07

Emergency patch release.

### Fixed

- [ISSUE DESCRIPTION]

### Reverted

- [WHAT WAS REVERTED IF APPLICABLE]
EOF

# 5. Run release gates
RUN_RELEASE_GATES=true ./scripts/gates/run-all-gates.sh

# 6. Create PR for hotfix
gh pr create --base main --title "Hotfix: v0.1.2" \
  --body "Emergency patch for SEV-1 issue. See #[ISSUE]"

# 7. After merge, tag and publish
git tag -a v0.1.2 -m "Release v0.1.2 (hotfix)"
git push origin v0.1.2

# 8. Trigger publish workflow
gh workflow run publish.yml -f tag=v0.1.2
```

### Handling Users Who Already Upgraded

#### Immediate Actions

1. **Post GitHub Discussion/Issue** with:
   - Clear title: "URGENT: v0.1.1 has critical issue - please downgrade"
   - Downgrade instructions
   - Impact explanation

2. **Update README** (temporarily):
   ```markdown
   > **Warning:** v0.1.1 has a known issue. Please use v0.1.0 until v0.1.2 is released.
   > See [Issue #XX](link) for details.
   ```

#### Downgrade Instructions Template

```markdown
## How to Downgrade

If you're affected by the issue in v0.1.1, downgrade with:

```bash
pip install motusos==0.1.0
```

### Verify the downgrade:

```bash
motus --version
# Should show 0.1.0
```

### If you have database issues after downgrade:

```bash
# Back up your data first
cp ~/.motus/coordination.db ~/.motus/coordination.db.backup

# Run doctor to check
motus doctor --fix
```
```

---

## Incident Response Procedures

### Triage Checklist

When an issue is reported:

```markdown
## Triage Checklist

### 1. Reproduction
- [ ] Can reproduce locally
- [ ] Reproduction steps documented
- [ ] Minimal reproduction case created

### 2. Scope Assessment
- [ ] Which versions affected?
- [ ] Which platforms affected? (macOS/Linux/Windows)
- [ ] Which Python versions affected?
- [ ] Estimated user impact (% of users)

### 3. Severity Determination
- [ ] Data integrity impact: YES / NO
- [ ] Security impact: YES / NO
- [ ] Core functionality impact: YES / NO
- [ ] Workaround exists: YES / NO

### 4. Classification
- [ ] Severity assigned: SEV-1 / SEV-2 / SEV-3 / SEV-4
- [ ] Response timeline set
- [ ] Owner assigned
```

### Bug vs Rollback-Worthy Decision Matrix

| Factor | Annoying Bug (No Rollback) | Rollback-Worthy |
|--------|---------------------------|-----------------|
| **Data** | Display issues | Data loss/corruption |
| **Frequency** | Edge cases | Common paths |
| **Workaround** | Exists and documented | None or complex |
| **Security** | No impact | Any vulnerability |
| **Recovery** | User can recover | Unrecoverable state |

### Incident Timeline Template

```markdown
## Incident Timeline: [TITLE]

**Incident ID:** INC-2026-01-07-001
**Severity:** SEV-X
**Status:** ACTIVE / MITIGATED / RESOLVED

### Timeline (All times UTC)

| Time | Event | Actor |
|------|-------|-------|
| 14:00 | Issue reported via GitHub | @user |
| 14:05 | Issue confirmed reproducible | @maintainer |
| 14:10 | Severity classified as SEV-1 | @maintainer |
| 14:15 | Rollback decision made | @maintainer |
| 14:20 | PyPI yank executed | @maintainer |
| 14:25 | GitHub announcement posted | @maintainer |
| 14:30 | Hotfix PR opened | @maintainer |
| 16:00 | Hotfix v0.1.2 published | @maintainer |
| 16:05 | Incident marked RESOLVED | @maintainer |

### Impact Summary
- Users affected: ~X
- Duration: X hours
- Data loss: YES/NO

### Root Cause
[Brief description]

### Resolution
[What was done to fix it]
```

---

## Communication Templates

### GitHub Issue: Incident Report (Internal)

```markdown
---
name: Incident Report
about: Document a post-release incident
labels: incident, priority-high
---

## Incident Summary

**Version:** vX.Y.Z
**Severity:** SEV-X
**Status:** INVESTIGATING / MITIGATED / RESOLVED

## Description

[What is happening]

## Impact

- **Who is affected:** [All users / Users who do X / etc.]
- **What is broken:** [Specific functionality]
- **Data impact:** [None / Read issues / Write issues / Data loss]

## Reproduction

```bash
# Steps to reproduce
```

## Workaround

[If any, or "None known"]

## Timeline

- [TIME] Issue discovered
- [TIME] [Action taken]

## Action Items

- [ ] Confirm reproduction
- [ ] Classify severity
- [ ] Determine response (rollback/hotfix/normal)
- [ ] Execute response
- [ ] Post user communication
- [ ] Schedule postmortem
```

### GitHub Discussion: User Announcement (SEV-1)

```markdown
# Urgent: Issue with v0.1.1 - Action Required

We've identified a critical issue in Motus v0.1.1 that affects [DESCRIPTION].

## What Happened

[Brief, non-technical explanation]

## Who Is Affected

[Clear description of affected users]

## What You Should Do

### If you haven't upgraded yet
Do not upgrade. Stay on v0.1.0:
```bash
pip install motusos==0.1.0
```

### If you already upgraded
Downgrade to the previous version:
```bash
pip install motusos==0.1.0
```

### If you've lost data
[Instructions or "Contact us at..."]

## What We're Doing

- We've removed v0.1.1 from the default installation path
- A fixed version (v0.1.2) is in progress
- Expected release: [TIME/DATE]

## Updates

We'll post updates in this thread. Subscribe to be notified.

---
**Last updated:** [TIMESTAMP]
```

### GitHub Discussion: User Announcement (SEV-2/3)

```markdown
# Known Issue in v0.1.1: [BRIEF DESCRIPTION]

We've identified an issue in Motus v0.1.1 that may affect some users.

## The Issue

[Clear description]

## Who Is Affected

[Specific conditions]

## Workaround

Until we release a fix:
```bash
# Workaround steps
```

## Fix Status

- **Fix PR:** #XXX
- **Expected release:** vX.Y.Z on [DATE]

No action required unless you're experiencing this issue.
```

### Tweet/Social (if applicable)

```
Heads up: We found an issue with motusos v0.1.1. If you upgraded today, please run:

pip install motusos==0.1.0

Fix coming in v0.1.2. Details: [LINK]

Sorry for the inconvenience.
```

---

## Postmortem Process

### When to Postmortem

- All SEV-1 incidents (required)
- SEV-2 incidents that took > 4 hours to resolve (required)
- Any incident with user data impact (required)
- SEV-3/4 if there are process learnings (optional)

### Postmortem Timeline

| Day | Action |
|-----|--------|
| Day 0 | Incident resolved |
| Day 1-2 | Draft postmortem document |
| Day 3-5 | Review with stakeholders |
| Day 5-7 | Publish postmortem |
| Day 7-14 | Implement action items |

### Postmortem Template

Create file: `docs/incidents/YYYY-MM-DD-incident-title.md`

```markdown
# Postmortem: [INCIDENT TITLE]

**Date:** YYYY-MM-DD
**Author:** @username
**Severity:** SEV-X
**Duration:** X hours
**User Impact:** X users affected

## Executive Summary

[2-3 sentences: what happened, impact, and outcome]

## Timeline

| Time (UTC) | Event |
|------------|-------|
| HH:MM | Event description |

## Root Cause

[What actually caused the issue - be specific]

## Detection

- **How was it found:** [User report / Monitoring / Testing]
- **Time to detect:** X minutes
- **Could we have detected sooner?** [Analysis]

## Response

- **Time to respond:** X minutes
- **Time to mitigate:** X minutes
- **Time to resolve:** X hours
- **Was the response appropriate?** [Analysis]

## Impact

- **Users affected:** X
- **Data impact:** [None / Corrupted / Lost]
- **Revenue impact:** [N/A for open source]
- **Reputation impact:** [Assessment]

## What Went Well

- [Positive observation 1]
- [Positive observation 2]

## What Went Wrong

- [Issue 1]
- [Issue 2]

## Lessons Learned

1. [Lesson 1]
2. [Lesson 2]

## Action Items

| ID | Action | Owner | Due Date | Status |
|----|--------|-------|----------|--------|
| 1 | [Action description] | @owner | YYYY-MM-DD | TODO |
| 2 | [Action description] | @owner | YYYY-MM-DD | TODO |

## Prevention

How will we prevent this class of issue in the future?

1. [Prevention measure 1]
2. [Prevention measure 2]

## Related

- Incident Issue: #XXX
- Fix PR: #XXX
- Related Issues: #XXX, #XXX
```

### Blameless Postmortem Principles

1. **Focus on systems, not people.** "The deployment process allowed X" not "Person Y deployed broken code"

2. **Assume good intent.** Everyone was trying to do the right thing with the information they had.

3. **Share openly.** Postmortems are public (unless security-sensitive). Transparency builds trust.

4. **Track action items.** Every postmortem must have concrete, assigned action items.

5. **Follow up.** Schedule a 30-day review to verify action items are complete.

---

## Prevention and Process Updates

### Release Gate Additions

After an incident, consider adding to release gates:

```yaml
# Example: Add to scripts/gates/
- gate-regression-001.sh  # Specific regression test
- gate-incident-001.sh    # Test for this incident class
```

### Documentation Updates

After postmortem, update:

| Document | Update Type |
|----------|-------------|
| This playbook | New procedures learned |
| `SECURITY.md` | New known limitations |
| Release checklist | New preflight checks |
| `gate-*.sh` scripts | New automated checks |

### Process Evolution Checklist

After each SEV-1/SEV-2 incident:

- [ ] Postmortem completed and published
- [ ] Action items assigned and tracked
- [ ] Release gates updated if applicable
- [ ] Monitoring/alerting improved if applicable
- [ ] Documentation updated
- [ ] Team retrospective scheduled (if warranted)

### Quarterly Review

Every quarter, review:

1. **Incident trends:** Are we seeing the same types of issues?
2. **Response times:** Are we getting faster or slower?
3. **Prevention effectiveness:** Did our action items prevent recurrence?
4. **Process gaps:** What incidents weren't covered by this playbook?

---

## Integration Points

### Existing Motus Infrastructure

This playbook integrates with:

| Component | Integration |
|-----------|-------------|
| `scripts/gates/gate-rollback-001.sh` | Verifies rollback capability pre-release |
| `scripts/gates/gate-release-001.sh` | Coordinates release artifacts |
| `.github/workflows/publish.yml` | PyPI publish workflow |
| `.github/workflows/release.yml` | GitHub release creation |
| `.github/ISSUE_TEMPLATE/release_checklist.md` | Pre-release verification |
| `docs/quality/release-evidence.json` | Release health attestation |
| `SECURITY.md` | Vulnerability reporting |

### Related Documents

- [`docs/quality/release-checklist.md`](release-checklist.md)
- [`CHANGELOG.md`](../../CHANGELOG.md)
- [`SECURITY.md`](../../SECURITY.md)
- [`.github/BRANCH-PROTECTION.md`](../../.github/BRANCH-PROTECTION.md)

---

## Quick Reference Card

### SEV-1 Response (< 30 minutes)

```
1. CONFIRM: Can you reproduce?
2. ASSESS: Data loss? Security? Core broken?
3. DECIDE: Rollback vs quick fix (30-min rule)
4. ACT: Yank or patch
5. COMMUNICATE: GitHub announcement
6. DOCUMENT: Incident issue + timeline
7. POSTMORTEM: Schedule within 48 hours
```

### Rollback Commands

```bash
# Yank from PyPI
twine yank motusos -v X.Y.Z

# User downgrade instruction
pip install motusos==X.Y.Z

# Verify rollback gate
./scripts/gates/gate-rollback-001.sh X.Y.Z PREV_VERSION
```

### Key Contacts

| Role | Contact |
|------|---------|
| Maintainer | Release maintainers (CODEOWNERS) |
| Security Issues | GitHub Security Advisories |
| PyPI Access | Maintainer only |

---

*This playbook is a living document. Update it after every incident.*
