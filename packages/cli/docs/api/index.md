# Motus API
Status: ACTIVE
Owner: DOCS_SPECS
Scope: Public-facing API documentation index
Version: 0.1
Date: 2025-12-30

Motus is usable both as a CLI (`motus ...`) and as a Python library. This directory documents the *public-ish* Python entry points that are stable enough for integrations and contributor onboarding.

If you only want the CLI, start with `README.md`. If you want to integrate Motus into another tool (CI, dashboards, exporters), start here.

## Quick Start (Programmatic)

```python
from motus.orchestrator import get_orchestrator

orch = get_orchestrator()
sessions = orch.discover_all(max_age_hours=24)

print(f"Found {len(sessions)} sessions")
if sessions:
    session = sessions[0]
    events = orch.get_events(session)
    print(f"{session.session_id}: {len(events)} events")
```

```python
from motus.orchestrator import get_orchestrator

orch = get_orchestrator()
sessions = orch.discover_all(max_age_hours=24)

if sessions:
    bundle = orch.export_teleport(sessions[0])
    print(bundle.session.session_id)
    print(len(bundle.events))
```

## Module Guides

- `coordination-api.md` — 6-call coordination facade (claim_work → release_work)
- `core-modules.md` — Config + orchestrator + core data flow
- `protocols.md` — Data model (sessions/events) and enums
- `builders.md` — Source-specific ingestors (Claude/Codex/Gemini)
- `integration.md` — Patterns for exports, dashboards, CI
- `extending.md` — Adding support for new sources (ingestor pattern)
