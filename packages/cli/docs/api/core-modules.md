# Core Modules

This page documents the “core” modules that integrations commonly use.

## `motus.config`

Centralized configuration for paths and runtime defaults.

- Primary entry point: `from motus.config import config`
- Environment variables:
  - `MC_VAULT_DIR`: optional pointer to a Vault OS directory (policy artifacts)
  - `MC_PORT`, `MC_HOST`, `MC_NO_BROWSER`: web UI settings

### Example: ensure state directories exist

```python
from motus.config import config

config.paths.ensure_dirs()
print(config.paths.logs_dir)
```

## `motus.logging`

Structured logging utilities used across the codebase.

- Primary entry point: `from motus.logging import get_logger`

### Example: structured log event

```python
from motus.logging import get_logger

log = get_logger("demo")
log.info("hello", subsystem="docs", ok=True)
```

## `motus.atomic_io`

Atomic file writes for crash safety (write temp → fsync → replace).

- `atomic_write_text(path, content)`
- `atomic_write_json(path, data, sort_keys=True, indent=2)`

### Example: atomic JSON write

```python
from pathlib import Path
from tempfile import TemporaryDirectory

from motus.atomic_io import atomic_write_json

with TemporaryDirectory() as tmp:
    path = Path(tmp) / "example.json"
    atomic_write_json(path, {"ok": True, "n": 1})
    print(path.read_text(encoding="utf-8"))
```

## `motus.orchestrator`

The orchestrator is the **single entry point** for session discovery and parsing across sources.

- Recommended entry point: `from motus.orchestrator import get_orchestrator`
- Also available: `SessionOrchestrator` class (lazy-imported)

### Example: create an orchestrator instance

```python
from motus.orchestrator import get_orchestrator

orch = get_orchestrator()
print(type(orch).__name__)
```

