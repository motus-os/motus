# Module Manager (Bundled Module Configuration)

Status: building
Roadmap: RI-MOD-060

## Purpose
Enable or disable bundled modules without breaking kernel invariants.

## Implementation Notes
- Module enablement is explicit and versioned.
- Kernel must function with modules disabled.
- Config defaults are read-only seeds.

## Best Practices
- Keep module toggles centralized.
- Avoid hidden dependencies between modules.
- Do not store kernel truth in module data stores.
