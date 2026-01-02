# Lens Engine (Context Assembly)

Status: building
Roadmap: RI-MOD-040

## Purpose
Assemble deterministic context bundles from contracts, knowledge, and evidence.

## Implementation Notes
- Bundle composition must be deterministic and cacheable.
- Missing prerequisites are explicit and reviewable.
- Hashes are stable for the same inputs.

## Best Practices
- List all inputs to the lens explicitly.
- Avoid hidden data sources.
- Store bundle hashes alongside attempts.
