# Contract Compiler (Standards Resolver)

Status: building
Roadmap: RI-MOD-020

## Purpose
Compile standards into deterministic contracts and hashes so work requirements are
stable, replayable, and auditable.

## Implementation Notes
- Contracts must compile deterministically for the same inputs.
- Contract hashes should be stored with attempts.
- Inputs are explicit and versioned.

## Best Practices
- Never mutate standards in place.
- Reject missing inputs early and clearly.
- Keep contract schemas minimal and stable.
