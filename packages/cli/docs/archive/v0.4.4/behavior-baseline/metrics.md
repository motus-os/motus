# v0.4.4 Baseline Metrics

**Captured:** 2025-12-04
**Branch:** v0.4.5-rebuild
**Tag:** v0.4.4-baseline

## Line Counts (Pre-Rebuild)

| File | Lines | Target |
|------|-------|--------|
| tui.py | 1,846 | ~700 |
| web.py | 1,140 | ~600 |
| cli.py | 1,748 | ~500 |
| **Total** | **4,734** | **~1,800** |

## Test Metrics

```
644 passed, 2 skipped, 10 warnings in 13.35s
```

## Known Issues (From Audit)

| Category | Count | Notes |
|----------|-------|-------|
| Silent exceptions | 17 | `except: pass` patterns |
| sys.path hacks | 3 | Import manipulation |
| f-string logging | 102+ | Non-structured logs |
| Deprecated but used | 4 | Modules marked deprecated |
| Type ignores | 15+ | Suppressed type errors |

## Dependencies

- Python 3.10+
- textual (TUI)
- aiohttp (Web)
- click (CLI)

## Post-Rebuild Targets

- Zero silent exceptions
- Zero sys.path hacks
- Zero f-string logging
- 800+ tests
- >90% coverage
