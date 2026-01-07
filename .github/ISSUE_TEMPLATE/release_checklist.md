---
name: Release checklist
about: Ship readiness checklist for a Motus release
labels: release
---

## Release target
- Version (vX.Y.Z):
- Target date:
- Owner:

## Preflight
- [ ] `CHANGELOG.md` updated for the release
- [ ] Version matches `packages/cli/pyproject.toml`
- [ ] Evidence artifacts updated in `packages/cli/docs/quality/`
- [ ] Public surfaces regenerated (`python scripts/generate-public-surfaces.py`)
- [ ] Tutorial validated (`python scripts/validate-tutorial.py --status-filter current`)
- [ ] Dependency lock updated (`packages/cli/uv.lock`)
- [ ] Release gates pass (`RUN_RELEASE_GATES=true ./scripts/gates/run-all-gates.sh`)
- [ ] Internal reference check clean

## Build + publish
- [ ] Tag pushed (vX.Y.Z)
- [ ] Draft release created (`release.yml`)
- [ ] PyPI publish completed (`publish.yml`) when releasing CLI
- [ ] Website deploy completed (`deploy-website.yml`) if site changed

## Post-release monitoring
- [ ] Release notes verified
- [ ] Demo repo artifacts attached (Validate Tutorial workflow)
- [ ] 24h review issue created (automatic via `post-release-24h.yml`)
- [ ] 24h review completed and closed
- [ ] 7d review issue created (automatic via `post-release-7d.yml`)
- [ ] 7d review completed with decision: STABLE / PATCH / HOTFIX
- [ ] 30d review scheduled (calendar reminder)
- [ ] Open defects triaged for the next release

## Post-release review links
<!-- Fill in after reviews are created -->
- 24h review: #
- 7d review: #
- 30d review: #

## Incident readiness
- [ ] Rollback gate verified (`./scripts/gates/gate-rollback-001.sh`)
- [ ] Previous version available on PyPI for rollback
- [ ] [Incident Response Playbook](../../docs/quality/INCIDENT-RESPONSE-PLAYBOOK.md) reviewed
- [ ] PyPI Trusted Publisher configured for `publish.yml`
