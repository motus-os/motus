# Motus

> The execution layer for AI agents.
> Models are powerful. Motus makes them capable.

[![License](https://img.shields.io/badge/license-MCSL-blue.svg)](LICENSE)
[![PyPI](https://img.shields.io/pypi/v/motusos)](https://pypi.org/project/motusos/)
[![Downloads](https://img.shields.io/pypi/dm/motusos)](https://pypi.org/project/motusos/)
[![CI](https://img.shields.io/badge/ci-private-lightgrey)](#)
[![Coverage](https://img.shields.io/badge/coverage-pending-lightgrey)](#)

Repository status: private until launch. Public links will activate at release.

## What is Motus?
Motus is a local-first coordination kernel for agent work. It provides a bounded
6-call facade for safe handoffs, verifiable evidence, and durable decisions,
backed by an append-only ledger.

## Why Motus?
- **Reduce drift**: one coordination contract across tools.
- **Prove changes**: evidence and decisions are first-class.
- **Bound context**: Lens-driven context cache prevents prompt sprawl.
- **Operate locally**: no SaaS lock-in, no hidden queues.

## Quickstart (10 lines)
```bash
pip install motusos
python - <<'PY'
from motus import Tracer
tracer = Tracer("quickstart")
tracer.thinking("hello motus")
tracer.decision("ship", reasoning="minimal example")
print("trace written")
PY
```

Expected output (example):
```
trace written
```
Trace files are stored locally in the Motus state directory.

Then open the dashboard:
```bash
motus web  # http://127.0.0.1:4000
```

## Proof and Implementation
- Website: https://motus-os.github.io/motus/
- Quickstart: https://motus-os.github.io/motus/quickstart/
- Implementation guide: https://motus-os.github.io/motus/implementation/
- Evidence registry: https://motus-os.github.io/motus/evidence/
- Ecosystem map: https://motus-os.github.io/motus/ecosystem/

## Documentation (canonical)
- [Implementation Guide](packages/cli/docs/implementation/README.md)
- [Kernel Guide](packages/cli/docs/implementation/kernel.md)
- [Module Registry](packages/cli/docs/standards/module-registry.yaml)
- [Docs Index](packages/cli/docs/README.md)

## Architecture and Governance
- [Architecture](ARCHITECTURE.md)
- [Security Policy](SECURITY.md)
- [Contributing](CONTRIBUTING.md)
- [Code of Conduct](CODE_OF_CONDUCT.md)
- [Changelog](CHANGELOG.md)

## Packages
| Package | Description |
|---------|-------------|
| [packages/cli](packages/cli/) | Python CLI and coordination kernel |
| [packages/website](packages/website/) | Documentation website |

## License
Motus Community Source License (MCSL). See [LICENSE](LICENSE).
