# Component Compliance Report (2026-01-02)

## Summary
All page-level patterns now use the shared primitives. Bespoke markup remains only for internal card content or one-off visuals.

## Page Checks
- `index.astro`: uses `SectionHeader`, `PersonaCard`, `ModuleCard`, `Panel` claim panels. OK.
- `how-it-works.astro`: uses `SectionHeader`, `MetricStat`, `Panel`. OK.
- `implementation.astro`: uses `SectionHeader`, `PersonaCard`, `Panel`. OK.
- `ecosystem.astro`: uses `SectionHeader`, `EcosystemFlow`, `Panel`. OK.
- `schema.astro`: uses `SectionHeader`, `Panel`. OK.
- `strategies.astro`: uses `SectionHeader`, `Panel`. OK.
- `open-source.astro`: uses `SectionHeader`, `Panel`. OK.
- `privacy.astro`: uses `SectionHeader`, `Panel`. OK.
- `terms.astro`: uses `SectionHeader`, `Panel`. OK.

## Notes
- `ProofChipRow` is available for proof chip bars but is not currently used.
- `MetricStat` is used only in the architecture explainer (`how-it-works.astro`).
