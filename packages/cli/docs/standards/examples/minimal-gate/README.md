# Minimal Gate Example

The simplest possible Motus gate implementation.

---

## Files

```
minimal-gate/
├── README.md         # This file
├── gate-check.sh     # The gate script
└── gates.json        # Gate configuration
```

---

## gate-check.sh

A gate is just a script that exits 0 (pass) or non-zero (fail):

```bash
#!/bin/bash
# gate-check.sh - Simplest possible gate

# Exit 0 = pass, non-zero = fail
echo "Running minimal gate check..."

# Your verification logic here
if [ -f "README.md" ]; then
    echo "README.md exists - PASS"
    exit 0
else
    echo "README.md missing - FAIL"
    exit 1
fi
```

---

## gates.json

Register the gate:

```json
{
  "version": "1.0.0",
  "tiers": [
    {"id": "T0", "name": "Tier 0", "description": "Basic checks"}
  ],
  "gates": [
    {
      "id": "gate-check",
      "tier": "T0",
      "kind": "artifact",
      "description": "Check that README exists",
      "command": "./gate-check.sh",
      "timeout_ms": 5000,
      "required": true
    }
  ]
}
```

---

## Usage

```bash
# Make executable
chmod +x gate-check.sh

# Run directly
./gate-check.sh

# Or via Motus
mc policy run --gates gate-check
```

---

## Extending

Add more gates by:

1. Creating another script (e.g., `gate-lint.sh`)
2. Adding an entry to `gates.json`
3. Optionally creating packs that use the new gate

---

## Key Points

- **Exit code matters:** 0 = pass, anything else = fail
- **stdout/stderr captured:** Output becomes evidence logs
- **Keep it simple:** Gate should be deterministic and fast
- **No secrets:** Gates don't receive sensitive env vars
