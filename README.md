<!-- GENERATED FILE - DO NOT EDIT DIRECTLY -->
<!-- Edit packages/cli/docs/website/messaging.yaml instead -->


# Motus

> What did your agent actually do? Motus knows.
> Every action logged. Every decision recorded. Every outcome a receipt.

[![License](https://img.shields.io/badge/license-MCSL-blue.svg)](LICENSE)
[![PyPI](https://img.shields.io/pypi/v/motusos)](https://pypi.org/project/motusos/)
[![Downloads](https://img.shields.io/pypi/dm/motusos)](https://pypi.org/project/motusos/)
[![Quality Gates](https://github.com/motus-os/motus/actions/workflows/quality-gates.yml/badge.svg)](https://github.com/motus-os/motus/actions/workflows/quality-gates.yml)

## Demo

![Motus claim-evidence-release loop](docs/assets/demo.gif)



## Quickstart

```bash
motus work claim TASK-001 --intent "My first task"
motus work evidence $LEASE test --passed 1
motus work release $LEASE success
```

Expected:
- You own this work.
- Proof attached.
- Receipt shipped.

## Benefits

- **Stop repeating work**: Stop re-explaining your codebase every session
- **Prove what happened**: Know what your AI did and why
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
