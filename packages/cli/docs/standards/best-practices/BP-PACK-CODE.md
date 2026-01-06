# BP-PACK-CODE: Code Scope Pack

> Version: 1.0.0
> Status: Active
> Precedence: 200 (overrides baseline)

---

## Purpose

Automatically escalate code-bearing changes to Tier T1 (tests run) while keeping documentation-only changes at Tier T0 (fast).

---

## Philosophy

**"Docs fast, code verified."**

Not all changes require the same rigor:
- README updates shouldn't trigger a full test suite
- Code changes should always run tests

This pack implements that calibration by scope-based tier selection.

---

## Scope Patterns

This pack applies when changes match any of these patterns:

```json
{
  "scopes": [
    "src/**",
    "tests/**",
    "pyproject.toml",
    "package.json",
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "Cargo.toml",
    "Cargo.lock",
    "Makefile",
    ".github/workflows/**"
  ]
}
```

### Why These Patterns?

| Pattern | Rationale |
|---------|-----------|
| `src/**` | Source code — must verify |
| `tests/**` | Test code — changes affect test outcomes |
| `pyproject.toml` | Python dependencies — may break things |
| `package.json` | JS dependencies — may break things |
| `*lock*` | Lock files — dependency changes |
| `Makefile` | Build scripts — affects build process |
| `.github/workflows/**` | CI config — affects pipeline |

---

## Configuration

### In registry.json

```json
{
  "id": "BP-PACK-CODE-TIER-T1",
  "precedence": 200,
  "scopes": ["src/**", "tests/**", ...],
  "gate_tier": "T1",
  "version": "1.0.0",
  "owner": "team",
  "status": "active"
}
```

### Precedence

- **100** = Baseline (catches everything at T0)
- **200** = Code pack (overrides baseline for code files)

Higher precedence wins. Code pack at 200 overrides baseline at 100.

---

## Behavior

### Case 1: Code Change

```
Changed files: ["src/main.py"]
Matching packs: [BP-PACK-BASELINE (100), BP-PACK-CODE-TIER-T1 (200)]
Selected: BP-PACK-CODE-TIER-T1 (highest precedence)
Gate tier: T1 (tests run)
```

### Case 2: Docs-Only Change

```
Changed files: ["README.md"]
Matching packs: [BP-PACK-BASELINE (100)]
Selected: BP-PACK-BASELINE
Gate tier: T0 (fast, no tests)
```

### Case 3: Mixed Change

```
Changed files: ["README.md", "src/main.py"]
Matching packs: [BP-PACK-BASELINE (100), BP-PACK-CODE-TIER-T1 (200)]
Selected: BP-PACK-CODE-TIER-T1 (any code file triggers escalation)
Gate tier: T1 (tests run)
```

---

## Benchmark Results

From kernel-0.1.1 calibration:

| Configuration | Prevention Rate | Friction (mean) |
|---------------|-----------------|-----------------|
| T0 only (no pack) | 75% | 737ms |
| T1 with code pack | 100% | 1139ms |

The code pack adds ~400ms friction but catches test failures that T0 misses.

---

## Customization

### Adding More Patterns

If your project has code in non-standard locations:

```json
{
  "scopes": [
    "src/**",
    "lib/**",        // Added
    "core/**",       // Added
    "tests/**"
  ]
}
```

### Creating T2 Pack

For security-critical code, create a higher-tier pack:

```json
{
  "id": "BP-PACK-SECURITY-TIER-T2",
  "precedence": 300,
  "scopes": ["src/auth/**", "src/crypto/**"],
  "gate_tier": "T2"
}
```

---

## Related Packs

- [BP-PACK-DOCS](BP-PACK-DOCS.md) — Fast-track documentation
- [Skill Template](skill-template.md) — Create custom packs

---

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2025-12-15 | Initial release |
