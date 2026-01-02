# Motus Website IA and Layout

## Site Map

- / (Home)
  - /how-it-works
  - /implementation
  - /strategies
  - /open-source
  - /schema
  - /privacy
  - /terms

Primary CTA: Install (motusos) or See How It Works. Secondary CTA: Implementation Guide.

## Navigation Structure

Primary nav (top): Home, How It Works, Implementation, Strategies, Open Source
Secondary nav (footer): Privacy, Terms, GitHub
In-page anchors: Each page supports anchors for long-form content.

## Page Templates

### Home

- Hero: one-sentence value proposition + two CTAs
- Problem / Solution split: agents work blind vs. Motus provides context
- Key features: 4 to 6 cards (Lens, Leases, Receipts, Strategies)
- Implementation wayfinding: clear path for builders to the Implementation Guide
- Architecture snapshot: diagram preview + link to How It Works
- Proof: reason codes and replayable evidence callout
- Open source trust block + GitHub link
- CTA band: Install

### How It Works

- Hero: The 6-call lifecycle overview
- Diagram: claim -> context -> outcome -> evidence -> decision -> release
- Lens assembly: sources -> compiler -> tiered output
- Evidence capture: replay tokens and audit trail
- Coordination: leases, snapshots, mutual exclusion
- CTA: Implementation Guide

### Implementation

- Hero: kernel + bundled modules explained
- Status semantics: current/building/future
- Kernel implementation: invariants + best practices
- Bundled modules: per-module best practices + roadmap IDs
- CTA: See module guides in docs

### Strategies

- Hero: reasoning patterns
- Strategy grid: 9 patterns
- Evidence: when to apply + triggers
- CTA: Apply in workflows

### Open Source

- Hero: trust, local-first, verifiable
- Proof: repos + policies
- CTA: GitHub

## Component Requirements

- Global: top nav, footer, CTA band
- Card grid (modules, strategies)
- Diagram block (supports SVG or inline diagram image)
- Reason code table
- Side-by-side problem/solution block
 - Implementation guide section

## Mobile Responsiveness Requirements

- Breakpoints: 360px, 768px, 1024px
- Navigation collapses to hamburger; CTA remains visible
- All multi-column grids stack to 1 column
- Diagrams scale to viewport width with 16:9 max aspect
- CTA bands use full-width buttons and 44px minimum tap targets
- Avoid heavy video; use lightweight SVG for diagrams
