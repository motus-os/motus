# Motus Website IA and Layout

## Site Map

- / (Home)
  - /how-it-works
  - /features
  - /use-cases
  - /pricing
  - /docs
  - /about

Primary CTA: Talk to Us (contact or demo request). Secondary CTAs: See How It Works, Read the Docs.

## Navigation Structure

Primary nav (top): Home, How It Works, Features, Use Cases, Docs, About, Talk to Us (button)
Secondary nav (footer): Privacy, Security, GitHub, Contact
In-page anchors: Each page supports a short anchor list for long-form content.

## Page Templates

### Home

- Hero: one-sentence value proposition + two CTAs
- Problem / Solution split: agents work blind vs. Motus provides context
- Key features: 4 to 6 cards (Context Cache, Lens, Coordination, Evidence, Tool Bridge, Policy Certificates)
- Architecture snapshot: diagram preview + link to How It Works
- Use cases preview: 3 cards with links
- Proof: reason codes and replayable evidence callout
- CTA band: Talk to Us

### How It Works

- Hero: The 4-call lifecycle overview
- Diagram: peek -> claim -> status -> release
- Lens assembly: sources -> compiler -> tiered output
- Evidence capture: replay tokens and audit trail
- Coordination: leases, snapshots, mutual exclusion
- CTA: Read the Docs

### Features

- Hero: capabilities overview
- Feature sections (one per capability):
  - Context Cache
  - Context Assembly
  - Context Delivery (Lens)
  - Tool Bridge (MCP)
  - Evidence Capture
  - Coordination
- Each section: 1 diagram + 2 to 3 bullet benefits

### Use Cases

- Hero: concrete outcomes
- Use case cards (3):
  - Multi-agent software delivery
  - CI/CD automation
  - Review and compliance automation
- Each card: problem, Motus impact, evidence artifact
- CTA: Talk to Us

### Pricing

- Hero: simple pricing framing
- Plans: Starter, Team, Enterprise (if unknown, use Contact Us placeholders)
- What is included: core features list
- CTA: Talk to Us

### Docs

- Hero: technical entry points
- Quick links: API, schemas, reason codes, examples
- Getting started: 3-step summary
- CTA: View API Reference

### About

- Hero: Veritas philosophy and mission
- Values: convivial tech, transparency, safety without friction
- Why Motus: knowledge plane positioning
- CTA: Contact

## Component Requirements

- Global: top nav, footer, CTA band
- Card grid (features, use cases, plans)
- Diagram block (supports SVG or inline diagram image)
- Reason code table
- Side-by-side problem/solution block

## Mobile Responsiveness Requirements

- Breakpoints: 360px, 768px, 1024px
- Navigation collapses to hamburger; CTA remains visible
- All multi-column grids stack to 1 column
- Diagrams scale to viewport width with 16:9 max aspect
- CTA bands use full-width buttons and 44px minimum tap targets
- Avoid heavy video; use lightweight SVG for diagrams
