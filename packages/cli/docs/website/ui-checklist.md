# Website UI Rhythm Checklist

Use this checklist to keep the site feeling deliberate, calm, and consistent.

## Layout rhythm

- Use `phi-*` spacing tokens for vertical rhythm and section padding.
- Sections own horizontal padding (`px-6 md:px-10`) so background bands can run full width.
- Wrap long-form content in `theme-light` to improve readability.
- Use `theme-dark` for dark panels inside light sections.
- Keep section cadence consistent: quiet section -> proof block -> CTA.
- Avoid dense grids; keep generous whitespace between blocks.
- Use theme tokens only (`surface`, `line`, `text-*`, `mint`, `error`) - no raw hex.
- Pair `text-text-primary` with `bg-surface`; reserve `text-text-secondary` for supporting copy.

## Typography

- Headings use `font-display` (Sora).
- Body copy uses `font-sans` (Sora).
- Code snippets use `font-mono` (JetBrains Mono).
- Avoid more than two font families in any section.

## Proof adjacency

- Every numeric claim includes a nearby proof link.
- If a claim cannot be proven, move it to Future or remove it.

## CTA discipline

- Primary CTA: one per section.
- Secondary CTA: optional, quieter style.
- Never introduce a third competing CTA in the same block.

## Components

- Use the Card component for module lists.
- Use rounded-2xl containers for major blocks.
- Keep borders subtle (`border-line/10` or `border-mint/20`).
