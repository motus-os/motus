# Python Project Example

A complete Motus governance setup for a Python project.

---

## Structure

```
python-project/
├── README.md           # This file
├── gates.json          # Gate definitions
├── profiles.json       # Profile configurations
├── registry.json       # Skill pack registry
├── gates/
│   ├── gate-lint.sh    # Ruff linting
│   └── gate-test.sh    # Pytest execution
└── evidence/           # Evidence bundles (generated)
```

---

## Quick Start

### 1. Install Dependencies

```bash
pip install ruff pytest
```

### 2. Make Gates Executable

```bash
chmod +x gates/*.sh
```

### 3. Run Governance

```bash
# Plan (see what would run)
mc policy plan --changed-files src/main.py

# Execute
mc policy run

# Verify
mc policy verify
```

---

## Configuration Files

### gates.json

Defines two tiers:
- **T0:** Lint only (fast)
- **T1:** Lint + tests (thorough)

```json
{
  "version": "1.0.0",
  "tiers": [
    {"id": "T0", "name": "Tier 0", "description": "Lint checks"},
    {"id": "T1", "name": "Tier 1", "description": "Lint + tests"}
  ],
  "gates": [
    {
      "id": "gate-lint",
      "tier": "T0",
      "kind": "lint",
      "command": "./gates/gate-lint.sh",
      "timeout_ms": 30000,
      "required": true
    },
    {
      "id": "gate-test",
      "tier": "T1",
      "kind": "test",
      "command": "./gates/gate-test.sh",
      "timeout_ms": 300000,
      "required": true
    }
  ]
}
```

### profiles.json

Two profiles:
- **personal:** T0 default, code escalates to T1
- **team:** T1 default, signature required

```json
{
  "version": "1.0.0",
  "profiles": [
    {
      "id": "personal",
      "description": "Solo developer, fast by default",
      "defaults": {"pack_cap": 8, "gate_tier_min": "T0"}
    },
    {
      "id": "team",
      "description": "Team environment, tests required",
      "defaults": {"pack_cap": 6, "gate_tier_min": "T1"}
    }
  ]
}
```

### registry.json

Two packs:
- **BP-PACK-BASELINE:** T0 for everything
- **BP-PACK-CODE:** T1 for code files

```json
{
  "version": "1.0.0",
  "packs": [
    {
      "id": "BP-PACK-BASELINE",
      "precedence": 100,
      "scopes": ["**/*"],
      "gate_tier": "T0",
      "version": "1.0.0",
      "owner": "team",
      "status": "active",
      "replacement": ""
    },
    {
      "id": "BP-PACK-CODE-TIER-T1",
      "precedence": 200,
      "scopes": ["src/**", "tests/**", "pyproject.toml"],
      "gate_tier": "T1",
      "version": "1.0.0",
      "owner": "team",
      "status": "active",
      "replacement": ""
    }
  ]
}
```

---

## Gate Scripts

### gates/gate-lint.sh

```bash
#!/bin/bash
set -e
echo "Running ruff lint..."
ruff check src/ tests/ || exit 1
echo "Lint passed"
```

### gates/gate-test.sh

```bash
#!/bin/bash
set -e
echo "Running pytest..."
pytest tests/ -q || exit 1
echo "Tests passed"
```

---

## Behavior Examples

### Docs-Only Change

```
Changed: README.md
Pack: BP-PACK-BASELINE (precedence 100)
Tier: T0
Gates: gate-lint
Result: Fast (~200ms)
```

### Code Change

```
Changed: src/main.py
Pack: BP-PACK-CODE-TIER-T1 (precedence 200)
Tier: T1
Gates: gate-lint, gate-test
Result: Thorough (~2s)
```

---

## Evidence Output

After `mc policy run`, find evidence in:

```
evidence/
└── 2025-12-15T10-30-00/
    ├── manifest.json    # Structured evidence
    └── logs/
        ├── gate-lint.stdout
        ├── gate-lint.stderr
        ├── gate-test.stdout
        └── gate-test.stderr
```

---

## Customization

### Add Security Gate

```json
{
  "id": "gate-security",
  "tier": "T2",
  "kind": "security",
  "command": "./gates/gate-security.sh",
  "timeout_ms": 60000,
  "required": true
}
```

### Add Security Pack

```json
{
  "id": "BP-PACK-SECURITY",
  "precedence": 300,
  "scopes": ["src/auth/**", "src/crypto/**"],
  "gate_tier": "T2",
  ...
}
```
