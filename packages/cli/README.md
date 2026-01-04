# Motus

> The execution layer for AI agents.
> Models are powerful. Motus makes them capable.

## What is Motus?
Motus is a local-first coordination kernel for agent work. It provides a single
6-call facade for safe handoffs, bounded context, and verifiable receipts, with
all state stored in `~/.motus/coordination.db`.

## Quick Start

```bash
pip install motusos
motus --help
motus web  # Opens dashboard at http://127.0.0.1:4000 (mc web alias)
```

## 6-call Coordination API (facade)

| Call | Purpose | Notes |
|------|---------|-------|
| `claim_work` | Reserve a work item and obtain a contract | Returns missing prerequisites |
| `get_context` | Assemble the current lens for the attempt | Returns missing prerequisites |
| `put_outcome` | Register primary deliverables | Outcome is not evidence |
| `record_evidence` | Attach verification artifacts | Typed + hashed evidence |
| `record_decision` | Append reasoning and approvals | Append-only |
| `release_work` | Finalize the attempt | Requires disposition + links |

## Core pillars

- **Scope**: bounded context via Lens and context cache.
- **Coordinate**: safe handoffs with the 6-call facade.
- **Verify**: receipts and governance gates you can audit.

## Example

```bash
python examples/hello_agent.py
```

## Documentation
- [Coordination API](docs/api/coordination-api.md)
- [Implementation Guide](docs/implementation/README.md)
- [Kernel Guide](docs/implementation/kernel.md)
- [Module Guides](docs/implementation/modules/)
- [Module Registry](docs/standards/module-registry.yaml)
- [Docs Index](docs/README.md)
- [Kernel Schema](docs/schema/index.md)
- [Architecture](docs/architecture.md)
- [CLI Reference](docs/cli-reference.md)
- [Terminology](docs/TERMINOLOGY.md)
- [Contributing](CONTRIBUTING.md)

## License
Motus Community Source License (MCSL). See `LICENSE`.
