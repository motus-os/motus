# Website Review Charter

This charter defines the definitive, recursive review process for the Motus website.
The goal is to deliver a crafted, proof-first experience that feels intentional for
each visitor type. Every phase produces artifacts that become the baseline for the
next phase.

## Principles

- Truth over theater: claims must be backed by evidence links.
- Component-driven: repeated patterns must use shared components.
- Token-only styling: spacing, color, and typography use tokens only.
- One primary CTA per section.

## Definition of Done

- Zero broken links, assets, or base-path issues.
- Every claim has an adjacent proof link or is explicitly marked future.
- All repeated patterns use shared components.
- All pages pass persona journey checks (see below).
- No bespoke spacing or colors outside the token system.

## Review Phases (recursive)

### Phase 0: Baseline Integrity

Goal: no breakage before subjective review.

Checklist:
- Base path is correct for deploy target.
- No broken images (logos, icons, diagram assets).
- No broken internal links.
- No console errors or 404s.
- Mobile nav works and is keyboard accessible.

Output:
- Phase 0 report (link list + asset list + 404 list).

### Phase 1: System Coherence (tokens + components)

Goal: ensure the design system enforces itself.

Checklist:
- Section headers use `SectionHeader`.
- Persona grids use `PersonaCard`.
- Module grids use `ModuleCard`.
- Proof chips use `ProofChipRow`.
- Metrics use `MetricStat` or are removed if unproven.
- Spacing uses `phi-*` tokens only.
- No raw hex; only theme tokens.

Output:
- Component compliance report (list of any bespoke markup).

### Phase 2: IA and Wayfinding

Goal: visitors can always see their next step.

Checklist:
- Navigation order matches the intended journey.
- Every page has a primary CTA.
- No orphan pages (every page is linked from nav or CTA).

Output:
- CTA map (page -> primary CTA -> destination).

### Phase 3: Proof-First Content

Goal: claims are factual, supported, and scoped.

Checklist:
- Proof links adjacent to claims.
- "Current/Building/Future" semantics applied consistently.
- Remove any claim without evidence.

Output:
- Claim ledger audit (claim -> proof link -> status).

### Phase 4: Persona Journey Drill-Down

Goal: each persona feels the site was crafted for them.

Paths:
- CTO/Architect: Hero -> Architecture -> Schema -> Governance -> Proof -> GitHub.
- Builder/Engineer: Hero -> Implementation -> Module registry -> Code examples -> CLI/API.
- Compliance/Risk: Proof model -> Audit trail -> Policy gates -> Data handling -> Repo.
- Product/Leadership: Vision -> Roadmap semantics -> Evidence -> Adoption path.

Output:
- Per-persona checklists with "3-click-to-proof" score.

### Phase 5: Visual Cadence and Emotion

Goal: section flow feels deliberate and effortless.

Checklist:
- Quiet -> proof -> CTA rhythm.
- No jarring shifts in tone or contrast.
- Headline hierarchy is consistent across pages.

Output:
- Cadence review notes (by section).

### Phase 6: Performance and Accessibility

Goal: fast and readable for all users.

Checklist:
- LCP and CLS within acceptable thresholds.
- Contrast meets WCAG.
- Focus states visible.
- Keyboard navigation works.

Output:
- Performance + accessibility report.

### Phase 7: Regression Pass

Goal: ensure fixes did not regress earlier phases.

Checklist:
- Re-run Phase 0, Phase 2, Phase 3.
- Validate component usage after changes.

Output:
- Final review sign-off.

## Persona Journey Success Criteria

- Each persona can reach proof in 3 clicks.
- Each persona sees a clear "next step" CTA on every page.
- The journey answers the persona's primary questions without detours.

## Review Artifacts (required)

- Phase 0 integrity report
- Component compliance report
- CTA map
- Claim ledger audit
- Persona journey checklists
- Final sign-off
