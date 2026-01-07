# Branch Protection: main

This repo assumes branch protection for `main` to keep releases consistent and auditable.

## Recommended Settings

- Require a pull request before merging
- Require at least 1 approval
- Dismiss stale approvals on new commits
- Require conversation resolution
- Require linear history (recommended)
- Restrict force pushes and deletions

## Required Status Checks

Require these checks to pass when they run (some are path-filtered):

- `Internal Reference Check`
- `Quality Gates`
- `Health Ledger`
- `Audit CLI ↔ Docs`
- `Validate Tutorial`

## Notes

- Release workflows (`release.yml`, `publish.yml`, `deploy-website.yml`) are tag/manual driven and do not block PRs.
- If a required check is path-filtered, it will only run when relevant files change.
