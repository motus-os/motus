# Phase 0 - Baseline Integrity (2026-01-02)

## Goal
Eliminate breakage before subjective review.

## Checks Performed
- Base path safety: no absolute internal href/src paths in `packages/website/src` (rg scan).
- Ecosystem logos: all `logo` entries in `packages/website/src/data/ecosystem-map.json` exist in `packages/website/public`.
- Brand assets present: `brand/motus-mark.svg`, `brand/noise.svg`.
- Anchor integrity: added missing anchors for `#proof-engine` and `#module-manager` on Implementation page.

## Results
- Base path usage: PASS (all internal links are base-prefixed).
- Ecosystem logos: PASS (no missing files).
- Brand assets: PASS (files present; if still broken post-deploy, check deploy base path).
- Anchors: PASS (anchors now exist).

## Notes
- GitHub Pages deploy requires `ASTRO_BASE=/motus` and the site must be viewed at `/motus/`.
- Build validation (`npm run build`) not executed in this pass.
