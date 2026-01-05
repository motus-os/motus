<!-- GENERATED FILE - DO NOT EDIT DIRECTLY -->
<!-- Edit packages/cli/docs/website/messaging.yaml instead -->


# Motus

> Agents do the work. Motus keeps the receipts.
> One API. Verification infrastructure for AI that acts.

[![License](https://img.shields.io/badge/license-MCSL-blue.svg)](LICENSE)
[![PyPI](https://img.shields.io/pypi/v/motusos)](https://pypi.org/project/motusos/)
[![Downloads](https://img.shields.io/pypi/dm/motusos)](https://pypi.org/project/motusos/)
[![Quality Gates](https://github.com/motus-os/motus/actions/workflows/quality-gates.yml/badge.svg)](https://github.com/motus-os/motus/actions/workflows/quality-gates.yml)

## Demo

![Motus claim-evidence-release loop](docs/assets/demo.gif)

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

## Evidence

- Six API calls run the full loop: claim, context, outcome, evidence, decision, release. ([Proof](https://motus-os.github.io/motus/docs/evidence#claim-six_call_api))
- The registry labels what is current, building, and future. ([Proof](https://motus-os.github.io/motus/docs/evidence#claim-module_registry))
- Kernel schema v0.1.3 defines the authoritative tables. ([Proof](https://motus-os.github.io/motus/docs/evidence#claim-kernel_schema))
- A registry sync gate keeps docs and website aligned. ([Proof](https://motus-os.github.io/motus/docs/evidence#claim-docs_registry_sync))

Full registry: https://motus-os.github.io/motus/docs/evidence

## Links

- Website: https://motus-os.github.io/motus/
- Get Started: https://motus-os.github.io/motus/get-started/
- How It Works: https://motus-os.github.io/motus/how-it-works/
- Docs: https://motus-os.github.io/motus/docs/
- PyPI: https://pypi.org/project/motusos/
- GitHub: https://github.com/motus-os/motus

## License

Motus Community Source License (MCSL). See https://github.com/motus-os/motus/blob/main/LICENSE.
