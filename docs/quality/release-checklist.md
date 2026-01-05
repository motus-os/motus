# Release Checklist

This checklist captures release-critical checks that keep the public surface in sync.

## Messaging + Docs
- [ ] Run `python3 scripts/generate-public-surfaces.py` and commit generated files.
- [ ] Run `python3 scripts/check-messaging-sync.py` and ensure all checks pass.

## Website Demo
- [ ] Re-run `scripts/demo/record-demo.sh` if CLI output changed.
- [ ] Verify `docs/assets/demo.gif` matches the current CLI output.
