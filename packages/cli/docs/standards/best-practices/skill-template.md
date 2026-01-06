# Skill Pack Template

> How to create custom skill packs for your project

---

## What is a Skill Pack?

A **skill pack** maps file scopes to gate tiers. It answers:

> "When these files change, what verification tier should run?"

---

## Pack Structure

Each pack is an entry in `registry.json`:

```json
{
  "id": "BP-PACK-YOUR-PACK",
  "path": "path/to/YOUR-PACK.md",
  "precedence": 200,
  "scopes": ["pattern/**"],
  "gate_tier": "T1",
  "coverage_tags": [],
  "version": "1.0.0",
  "owner": "your-team",
  "status": "active",
  "replacement": ""
}
```

---

## Required Fields

| Field | Description | Example |
|-------|-------------|---------|
| `id` | Unique pack identifier | `BP-PACK-AUTH-TIER-T2` |
| `precedence` | Priority (higher wins) | `300` |
| `scopes` | Glob patterns to match | `["src/auth/**"]` |
| `gate_tier` | Required tier when matched | `T2` |
| `version` | Semver version | `1.0.0` |
| `owner` | Maintainer | `security-team` |
| `status` | `active` or `deprecated` | `active` |

---

## Optional Fields

| Field | Description | Example |
|-------|-------------|---------|
| `path` | Documentation path | `docs/packs/AUTH.md` |
| `coverage_tags` | Compliance tags | `["SOC2:CC6.1"]` |
| `replacement` | If deprecated, what replaces it | `BP-PACK-AUTH-V2` |

---

## Precedence Rules

| Range | Usage |
|-------|-------|
| 100 | Baseline (catch-all) |
| 200 | Domain-specific (code, docs) |
| 300 | High-risk (security, auth) |
| 400+ | Critical (compliance, regulated) |

Higher precedence wins when multiple packs match.

---

## Example: Security Pack

```json
{
  "id": "BP-PACK-SECURITY-TIER-T2",
  "path": "best-practices/SECURITY.md",
  "precedence": 300,
  "scopes": [
    "src/auth/**",
    "src/crypto/**",
    "src/security/**",
    "**/*secret*",
    "**/*credential*"
  ],
  "gate_tier": "T2",
  "coverage_tags": ["OWASP:all", "SOC2:CC6.1"],
  "version": "1.0.0",
  "owner": "security-team",
  "status": "active",
  "replacement": ""
}
```

---

## Example: Infrastructure Pack

```json
{
  "id": "BP-PACK-INFRA-TIER-T1",
  "path": "best-practices/INFRA.md",
  "precedence": 250,
  "scopes": [
    "terraform/**",
    "kubernetes/**",
    "docker/**",
    "Dockerfile*",
    ".github/workflows/**"
  ],
  "gate_tier": "T1",
  "coverage_tags": ["CDIO:deployment"],
  "version": "1.0.0",
  "owner": "platform-team",
  "status": "active",
  "replacement": ""
}
```

---

## Documentation Template

Create a markdown file for each pack:

```markdown
# BP-PACK-YOUR-PACK: Description

> Version: 1.0.0
> Status: Active
> Precedence: NNN

---

## Purpose

[Why this pack exists]

---

## Scope Patterns

[List patterns and explain why each is included]

---

## Gate Tier

[Which tier and why]

---

## Customization

[How to extend or modify]

---

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | YYYY-MM-DD | Initial release |
```

---

## Testing Your Pack

### 1. Add to registry.json

```json
{
  "packs": [
    // ... existing packs
    { "id": "BP-PACK-YOUR-PACK", ... }
  ]
}
```

### 2. Verify matching

```bash
# Test which pack matches a file
mc policy plan --changed-files src/auth/login.py --dry-run
```

### 3. Confirm tier

The plan output should show your pack and its tier.

---

## Best Practices

### DO

- Use specific patterns (not `**/*` unless baseline)
- Document why each pattern is included
- Set precedence appropriately (don't override security packs with lower-risk packs)
- Version your packs

### DON'T

- Create overlapping packs at the same precedence
- Use very high precedence (400+) unless truly critical
- Forget to update docs when changing patterns

---

## Related

- [BP-PACK-CODE](BP-PACK-CODE.md) — Example code pack
- [BP-PACK-DOCS](BP-PACK-DOCS.md) — Example docs pack
- [registry.json schema](../schemas/registry.json) — Validation schema
