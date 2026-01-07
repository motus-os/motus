# Contributing to Motus

## Repository Layout

- `packages/cli/` - Motus CLI and core runtime
- `packages/website/` - Marketing website (Astro)
- `scripts/gates/` - Release gate scripts (registered in `packages/cli/docs/standards/gates.yaml`)
- `scripts/` - Repo sync and verification utilities

## Development Setup

```bash
git clone https://github.com/motus-os/motus
cd motus/packages/cli
python3 -m venv venv
source venv/bin/activate
pip install -e ".[dev]"

# Verify installation
motus --help
python3 -m pytest tests/ -q
```

## Website Setup

```bash
cd motus/packages/website
npm ci
npm run dev
```

## Running Tests

```bash
python3 -m pytest tests/ -v
python3 -m pytest tests/test_<name>.py -v
```

## Code Style

```bash
ruff check src/
ruff check src/ --fix
```

## Quality Gates (Recommended Before PR)

CLI checks:

```bash
cd motus
./scripts/gates/run-all-gates.sh
```

Release-only gates:

```bash
RUN_RELEASE_GATES=true ./scripts/gates/run-all-gates.sh
```

Website sync checks (when changing website or messaging):

```bash
python scripts/generate-public-surfaces.py
python scripts/check-messaging-sync.py
python scripts/check-chapters-sync.py
```

Tutorial validation (when tutorial or CLI behavior changes):

```bash
python scripts/validate-tutorial.py --status-filter current
```

## Pull Request Process

1. Create feature branch
2. Make changes
3. Run tests: `python3 -m pytest tests/ -q`
4. Run linter: `ruff check src/`
5. Run relevant quality gates (see above)
6. Commit with clear message
7. Push and create PR

## Commit Messages

Format: `type: description`

Types: feat, fix, docs, test, refactor, style, chore
