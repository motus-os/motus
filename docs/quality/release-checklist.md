# Release Checklist

This checklist captures release-critical checks that keep the public surface in sync.

## Messaging + Docs
- [ ] Run `python3 scripts/generate-public-surfaces.py` and commit generated files.
- [ ] Run `python3 scripts/check-messaging-sync.py` and ensure all checks pass.
- [ ] Update `packages/cli/uv.lock` for dependency reproducibility.

## Website Demo
- [ ] Re-run `scripts/demo/record-demo.sh` if CLI output changed.
- [ ] Verify `docs/assets/demo.gif` matches the current CLI output.
- [ ] Re-run `packages/website/benchmark/run.sh` if the homepage comparison or token-reduction claim changed.

## Incident Readiness
- [ ] Rollback gate passes (`./scripts/gates/gate-rollback-001.sh`)
- [ ] Previous version confirmed available on PyPI
- [ ] Review [Incident Response Playbook](./INCIDENT-RESPONSE-PLAYBOOK.md) for any updates needed
- [ ] Verify PyPI Trusted Publisher is configured for `publish.yml`
