# Manual GitHub Setup Checklist

This document lists GitHub settings that must be configured manually via the GitHub UI. These cannot be set via code or CI.

## Branch Protection (Required)

**Navigate to**: Settings → Branches → Add rule for `main`

| Setting | Value |
|---------|-------|
| Require pull request reviews | Yes |
| Required approving reviews | 1 |
| Dismiss stale PR reviews | Yes |
| Require status checks to pass | Yes |
| Required checks | `hygiene-gates`, `messaging-sync`, `package-validation` |
| Require branches to be up to date | Yes |
| Require conversation resolution | Yes |

## PyPI Trusted Publishing (Required for Release)

**Navigate to**: PyPI project settings → Publishing → Add a Trusted Publisher

Required settings:

| Field | Value |
|-------|-------|
| Owner | `motus-os` |
| Repository | `motus` |
| Workflow | `publish.yml` |
| Environment | `pypi` |

**Note**: No PyPI API token should be stored in GitHub secrets for publishing.

## GitHub Actions Permissions (Verify)

**Navigate to**: Settings → Actions → General

| Setting | Value |
|---------|-------|
| Actions permissions | Allow all actions |
| Workflow permissions | Read and write |
| Allow GitHub Actions to create PRs | Yes |

## Security Settings (Recommended)

**Navigate to**: Settings → Code security and analysis

| Setting | Status |
|---------|--------|
| Dependency graph | Enabled |
| Dependabot alerts | Enabled |
| Dependabot security updates | Enabled |
| Secret scanning | Enabled |
| Push protection | Enabled |

## Repository Features (Verify)

**Navigate to**: Settings → General

| Feature | Status |
|---------|--------|
| Issues | Enabled |
| Projects | Optional |
| Wiki | Disabled (docs in repo) |
| Discussions | Optional |

---

## Verification Commands

After manual setup, verify with:

```bash
# Check branch protection via API
gh api repos/{owner}/{repo}/branches/main/protection

# Check secrets are set (won't show values)
gh secret list

# Check Actions permissions
gh api repos/{owner}/{repo}/actions/permissions
```

---

*Document created: 2026-01-07*
*Last updated: 2026-01-07*
