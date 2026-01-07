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
- [ ] Release gates pass (`RUN_RELEASE_GATES=true ./scripts/gates/run-all-gates.sh`)
- [ ] Internal reference check clean

## Build + publish
- [ ] Tag pushed (vX.Y.Z)
- [ ] Draft release created (`release.yml`)
- [ ] PyPI publish completed (`publish.yml`) when releasing CLI
- [ ] Website deploy completed (`deploy-website.yml`) if site changed

## Post-release
- [ ] Release notes verified
- [ ] Demo repo artifacts attached (Validate Tutorial workflow)
- [ ] Open defects triaged for the next release
