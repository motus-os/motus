<!-- GENERATED FILE - DO NOT EDIT DIRECTLY -->
<!-- Edit packages/cli/docs/website/messaging.yaml instead -->


# Motus

> Your AI agents waste 66% of their work. Motus makes every action verifiable.
> Claim work. Prove it's done. One API. Ship receipts, not trust.

[![License](https://img.shields.io/badge/license-MCSL-blue.svg)](LICENSE)
[![PyPI](https://img.shields.io/pypi/v/motusos)](https://pypi.org/project/motusos/)
[![Downloads](https://img.shields.io/pypi/dm/motusos)](https://pypi.org/project/motusos/)

## Install

```bash
pip install motusos
```
Expected: CLI installs successfully

## Quickstart

```bash
pip install motusos
motus init --lite --path . && motus doctor
motus work claim TASK-001 --intent "My first task"
motus work evidence $LEASE test --passed 1
motus work release $LEASE success
motus work status $LEASE
```

Expected:
- CLI installs successfully
- Health checks pass
- Lease ID returned (e.g., lease_abc123)
- Evidence recorded
- Receipt shows outcome + evidence
- Full receipt displayed

## Benefits

- **Stop repeating work**: Every action is tracked and proven
- **Prove what happened**: Receipts, not trust
- **No cloud required**: Local-first, your data stays yours

## Links

- Website: https://motus-os.github.io/motus/
- Get Started: https://motus-os.github.io/motus/get-started/
- How It Works: https://motus-os.github.io/motus/how-it-works/
- Docs: https://motus-os.github.io/motus/docs/
- PyPI: https://pypi.org/project/motusos/
- GitHub: https://github.com/motus-os/motus

## License

Motus Community Source License (MCSL). See https://github.com/motus-os/motus/blob/main/LICENSE.
