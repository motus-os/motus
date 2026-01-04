# Ecosystem Flowchart Replacement Plan

Goal: Replace the current ecosystem page with a system flowchart that shows the full Motus vision, including future IP sharing, with explicit status coloring and proof links.

## Status Color System
- Current: neutral surface (no accent), mint dot only.
- Building: mint border + badge.
- Future: purple border + badge.

## Naming (Future Layer)
- Work Ledger (Future): signed work receipts + provenance.
- Asset Registry (Future bundled module): IP assets, owners, license terms.
- Motus Exchange (Future): brokerage for licensed IP + work execution.

## Phased Delivery

### Phase 1: Trust Fixes (Proof + Legal)
- RI-WEB-015: Align website code examples with real APIs.
- RI-WEB-017: Legal copy alignment with MCSL license.
- RI-WEB-018: Schema CTA + proof link fixes.

Acceptance:
- No sample code references missing APIs.
- Legal copy matches repo license.
- All proof links resolve.

### Phase 2: Flowchart Replacement
- RI-WEB-012: Replace ecosystem page with flowchart view.
- RI-WEB-013: Add IP-sharing layer (Work Ledger, Asset Registry, Motus Exchange).
- RI-WEB-016: Status color system (current/building/future).

Acceptance:
- Flowchart reads left-to-right on desktop, top-to-bottom on mobile.
- Every node shows status and has a proof link or roadmap ID.
- Future nodes are clearly marked and not implied as shipped.

### Phase 3: Page Alignment
- RI-WEB-014: Implementation page Start Here flow.
- Update homepage CTA to Ecosystem Flow + Implementation Guide.
- Reduce OODA dominance on How It Works; keep as footnote.

Acceptance:
- Implementation page reads as a linear onboarding sequence.
- Ecosystem Flow becomes the canonical system view.
- No duplicate module lists across pages.

## Test / Review
- npm run build
- Manual proof link check
- Mobile readability check (flowchart and badges)
