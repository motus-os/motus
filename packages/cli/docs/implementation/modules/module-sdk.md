# Module SDK (Interface Layer)

Status: building
Roadmap: RI-MOD-001

## Purpose
Define the interfaces and toggle behavior for bundled modules so the kernel can
operate with modules disabled.

## Implementation Notes
- Interfaces must be explicit and versioned.
- Module-off behavior returns deterministic `missing_prereqs`.
- Kernel APIs remain the only write path to coordination.db.

## Best Practices
- Keep interfaces minimal and stable.
- Test all module-off combinations.
- Never allow modules to bypass kernel invariants.
