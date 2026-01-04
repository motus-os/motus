# Contributing to Motus

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

## Pull Request Process

1. Create feature branch
2. Make changes
3. Run tests: `python3 -m pytest tests/ -q`
4. Run linter: `ruff check src/`
5. Commit with clear message
6. Push and create PR

## Commit Messages

Format: `type: description`

Types: feat, fix, docs, test, refactor, style, chore
