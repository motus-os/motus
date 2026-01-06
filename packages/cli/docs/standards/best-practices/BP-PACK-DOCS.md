# BP-PACK-DOCS: Documentation Fast-Track Pack

> Version: 1.0.0
> Status: Active
> Precedence: 100 (baseline)

---

## Purpose

Fast-track documentation-only changes with minimal friction (Tier T0).

---

## Philosophy

**"Don't block README fixes on test suites."**

Documentation changes rarely break production code. Running the full test suite for a typo fix is wasted friction.

This pack ensures docs-only changes get:
- Fast feedback (lint only)
- Minimal overhead (~200ms)
- Still governed (evidence produced)

---

## Scope Patterns

This pack is the **baseline** — it matches everything that more specific packs don't override:

```json
{
  "scopes": ["**/*"]
}
```

### Effective Behavior

The baseline pack catches:
- `README.md`
- `docs/**`
- `*.md`
- `LICENSE`
- `.gitignore`
- Any file not matched by a higher-precedence pack

---

## Configuration

### In registry.json

```json
{
  "id": "BP-PACK-BASELINE",
  "precedence": 100,
  "scopes": ["**/*"],
  "gate_tier": "T0",
  "version": "1.0.0",
  "owner": "team",
  "status": "active"
}
```

### Precedence

At 100, this is the lowest priority pack. Any more specific pack will override it.

---

## Gates at T0

Tier T0 typically includes:

| Gate | Purpose | Time |
|------|---------|------|
| Format check | Ensure consistent formatting | ~50ms |
| Lint | Catch obvious issues | ~100ms |
| Schema validation | Verify config files | ~50ms |

**Not included at T0:**
- Test suite (T1)
- Security scan (T2)
- Coverage check (T1)

---

## When This Pack Applies

### Pure Docs

```
Changed files: ["README.md", "docs/api.md"]
Matching packs: [BP-PACK-BASELINE (100)]
Gate tier: T0
```

### Mixed (Overridden)

```
Changed files: ["README.md", "src/main.py"]
Matching packs: [BP-PACK-BASELINE (100), BP-PACK-CODE (200)]
Gate tier: T1 (code pack takes precedence)
```

---

## Creating a Specific Docs Pack

If you want special handling for docs (e.g., spell check), create a pack:

```json
{
  "id": "BP-PACK-DOCS-SPELLCHECK",
  "precedence": 150,
  "scopes": ["docs/**", "*.md"],
  "gate_tier": "T0",
  "gates": ["gate-spellcheck"]
}
```

This runs at T0 but adds a spell check gate for markdown files.

---

## Related Packs

- [BP-PACK-CODE](BP-PACK-CODE.md) — Code changes require T1
- [Skill Template](skill-template.md) — Create custom packs

---

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2025-12-15 | Initial release |
