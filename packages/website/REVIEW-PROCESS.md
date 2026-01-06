# Motus Website Review Process

**Version**: 1.0
**Created**: 2026-01-06
**Purpose**: Comprehensive multi-phased review process for website development

---

## Ethos & Brand Positioning

### Core Identity

**Motus exists to make AI agent work verifiable.**

We solve the fundamental problem: when an AI agent does work, there's no structured record of what actually happened. Motus provides receipts—immutable records of outcomes, evidence, and decisions.

### Brand Principles

| Principle | Meaning | Anti-Pattern |
|-----------|---------|--------------|
| **Clarity over cleverness** | Plain language, concrete nouns | Jargon, vague claims, marketing fluff |
| **Proof over promise** | Every claim links to evidence | Unverified statistics, aspirational statements |
| **Developer respect** | Assume intelligence, not knowledge | Condescension, over-explanation, hype |
| **Mathematical precision** | Design system enforced, not suggested | Arbitrary values, "close enough" |

### Voice

- **Confident, not arrogant**: We know what we built. We don't oversell it.
- **Technical, not exclusionary**: Developers are our audience, but clarity serves everyone.
- **Direct, not cold**: Short sentences. Active voice. Human warmth.

### Visual Identity

- **Phi-based spacing**: All spacing derives from Fibonacci sequence (8, 13, 21, 34, 55, 89, 144, 233px)
- **OKLCH color palette**: Perceptually uniform, mathematically defined
- **Typography**: Sora (display), JetBrains Mono (code)
- **Accent**: Mint (#66FFDE in hex, oklch 60% 0.16 170)

---

## Phase 0: Foundation Verification

**Purpose**: Ensure all prerequisites exist before any work begins.

### Tasks

| Task | Description | Deliverable |
|------|-------------|-------------|
| 0.1 | Verify design system exists and is documented | `tailwind.config.mjs` reviewed |
| 0.2 | Verify brand guidelines exist | Voice doc, color palette, typography |
| 0.3 | Verify deployment pipeline works | Successful test deploy |
| 0.4 | Verify correct repository | Working directory confirmed |
| 0.5 | Document constraints | List of non-negotiables |

### Success Criteria

- [ ] Design system file exists with phi spacing, oklch colors
- [ ] Can deploy to production (GitHub Pages) and verify
- [ ] All team members know the correct repo location
- [ ] Brand voice document exists and is referenced

### Confidence Definition

**100% confident** when: All deliverables exist as files, deployment succeeds, no ambiguity about where to work.

---

## Phase 1: Research

**Purpose**: Ground all decisions in world-class precedent before writing any code.

### 1A: Competitive & Inspirational Research

Research these companies for patterns:

| Company | Why | What to Study |
|---------|-----|---------------|
| **Stripe** | Gold standard developer docs | Information hierarchy, code examples, trust signals |
| **Vercel** | Developer-first landing pages | Hero patterns, feature sections, dark mode |
| **Linear** | Product-led growth | Minimalism, motion, value communication |
| **Cursor** | AI tool positioning | How they explain AI to developers |
| **Anthropic** | AI safety/trust messaging | How they build credibility |
| **OpenAI** | API documentation | Code examples, getting started flow |
| **Google** | Material Design | Component patterns, accessibility |
| **MIT** | Academic credibility | How they present research, citations |

### 1B: Pattern Extraction

For each section type, document:

```markdown
## [Section Type] Patterns

### Sources Reviewed
- [URL 1]: Key insight
- [URL 2]: Key insight

### Common Patterns
1. Pattern A (seen in X, Y, Z)
2. Pattern B (seen in A, B)

### Anti-Patterns
1. What to avoid (why)

### Decision
We will use [pattern] because [reason].
```

### 1C: Evidence Gathering

For any quantitative claim:

| Claim | Required Evidence | Minimum Standard |
|-------|-------------------|------------------|
| Performance (ms) | Benchmark results | N ≥ 1,000, p50/p95/p99 reported |
| Reduction (%) | A/B comparison | Real tokenizer (tiktoken), reproducible |
| Compatibility | Test matrix | Actual test runs, not assumptions |
| User metrics | Analytics data | Statistical significance |

### Tasks

| Task | Description | Deliverable |
|------|-------------|-------------|
| 1.1 | Research hero patterns from 5+ sources | Pattern document |
| 1.2 | Research section layouts from 5+ sources | Pattern document |
| 1.3 | Research code example presentation | Pattern document |
| 1.4 | Research trust/credibility signals | Pattern document |
| 1.5 | Gather all quantitative evidence | Evidence bundle per claim |

### Success Criteria

- [ ] Each pattern decision cites 3+ world-class sources
- [ ] No quantitative claim without evidence bundle
- [ ] Research documents saved for future reference
- [ ] Team has reviewed and approved patterns

### Confidence Definition

**100% confident** when: Every design decision traces to documented research. Every number traces to reproducible evidence.

---

## Phase 2: Information Architecture

**Purpose**: Define what content exists and how it's organized before writing copy.

### 2A: Page Inventory

| Page | Purpose | Primary CTA | Success Metric |
|------|---------|-------------|----------------|
| Homepage | Explain what Motus is, drive installation | `pip install motusos` | Install clicks |
| How It Works | Explain the 6-call API | View docs | Doc pageviews |
| Get Started | First receipt in 5 minutes | Complete tutorial | Tutorial completion |
| Docs | Reference documentation | N/A | Time on page |

### 2B: Section Structure

For each page, define:

```markdown
## [Page Name] Structure

### Above the Fold
- Headline: [exact text]
- Subheadline: [exact text]
- Primary CTA: [text] → [destination]
- Visual: [description]

### Section 1: [Name]
- Purpose: [what this accomplishes]
- Headline: [exact text]
- Content type: [comparison/demo/testimonial/etc]
- Evidence required: [what proof backs this]

### Section N...
```

### 2C: Content Requirements

| Content Type | Requirements |
|--------------|--------------|
| Headlines | ≤8 words, no jargon, passes 5-second test |
| Subheadlines | One sentence, concrete benefit |
| Body copy | Grade 8 reading level, active voice |
| Code examples | Runnable, syntax highlighted, annotated |
| Claims | Link to evidence, qualified if uncertain |

### Tasks

| Task | Description | Deliverable |
|------|-------------|-------------|
| 2.1 | Define page inventory | Page list with purposes |
| 2.2 | Define section structure per page | Section outline document |
| 2.3 | Write all headlines | Headline document |
| 2.4 | Map evidence to claims | Evidence mapping |
| 2.5 | Review with fresh eyes | Outsider comprehension test |

### Success Criteria

- [ ] Every section has a defined purpose
- [ ] Every headline passes the "can I visualize it?" test
- [ ] Every claim maps to evidence or is marked "unverified"
- [ ] Someone unfamiliar with Motus understands the structure

### Confidence Definition

**100% confident** when: A non-technical person can explain what each section is for after reading the outline.

---

## Phase 3: Visual Design

**Purpose**: Define how content will look before building.

### 3A: Design System Compliance

Every visual decision must use design tokens:

| Element | Allowed Values | Source |
|---------|----------------|--------|
| Spacing | phi-1 through phi-8 | `tailwind.config.mjs` |
| Colors | charcoal, surface, surface-muted, line, mint, error, text-primary, text-secondary | CSS variables |
| Typography | text-xs through text-6xl | Font scale |
| Radii | rounded-sm through rounded-xl | Border radius tokens |
| Shadows | shadow-soft, shadow-lift | Shadow tokens |

**No arbitrary values.** If a value isn't in the design system, add it to the system first.

### 3B: Component Inventory

Before building, list all components needed:

| Component | Exists? | Needs Update? | Design System Compliant? |
|-----------|---------|---------------|-------------------------|
| Section | Yes | No | Yes |
| Panel | Yes | No | Yes |
| Button | Yes | No | Yes |
| CodeBlock | No | N/A | Must create |

### 3C: Responsive Strategy

| Breakpoint | Name | Behavior |
|------------|------|----------|
| < 640px | Mobile | Single column, stacked elements |
| 640-768px | Tablet | Two columns where appropriate |
| > 768px | Desktop | Full layout |

### Tasks

| Task | Description | Deliverable |
|------|-------------|-------------|
| 3.1 | Audit existing components | Component inventory |
| 3.2 | Design new components (if needed) | Component specs |
| 3.3 | Define section layouts | Layout specs per section |
| 3.4 | Verify responsive behavior | Breakpoint documentation |
| 3.5 | Review for design system compliance | Compliance checklist |

### Success Criteria

- [ ] Zero arbitrary values in any design
- [ ] All components documented
- [ ] Mobile layouts defined for every section
- [ ] Design system audit passes

### Confidence Definition

**100% confident** when: Every pixel traces to a design token. No "magic numbers."

---

## Phase 4: Implementation

**Purpose**: Build the pages with quality gates at each step.

### 4A: Implementation Order

1. **Layout structure** - Sections, spacing, grid
2. **Typography** - Headlines, body, code
3. **Colors** - Backgrounds, text, accents
4. **Components** - Buttons, panels, code blocks
5. **Content** - Copy, images, links
6. **Interactivity** - Hover states, animations

### 4B: Quality Gates

Before moving to next step:

| Gate | Check |
|------|-------|
| After Layout | Sections have correct padding, max-widths |
| After Typography | Font sizes match design system |
| After Colors | All colors from palette, theme-aware |
| After Components | Components render correctly in both themes |
| After Content | All copy matches approved content |
| After Interactivity | Animations use design system timing |

### 4C: Code Standards

```astro
<!-- GOOD: Design system classes -->
<div class="p-phi-4 bg-surface text-text-primary rounded-lg">

<!-- BAD: Arbitrary values -->
<div class="p-6 bg-[#1a1a1a] text-gray-100 rounded-[10px]">
```

### Tasks

| Task | Description | Deliverable |
|------|-------------|-------------|
| 4.1 | Build section structure | Sections render |
| 4.2 | Apply typography | Text styled |
| 4.3 | Apply colors | Colors correct |
| 4.4 | Build/integrate components | Components work |
| 4.5 | Populate content | Copy in place |
| 4.6 | Add interactivity | Animations work |
| 4.7 | Pass all quality gates | Checklist complete |

### Success Criteria

- [ ] Page renders without errors
- [ ] All design system classes used (no arbitrary values)
- [ ] Content matches approved copy
- [ ] Components work in isolation and in context

### Confidence Definition

**100% confident** when: Code review shows zero arbitrary values, page matches design spec exactly.

---

## Phase 5: Technical Review

**Purpose**: Verify code quality, accessibility, and performance.

### 5A: Accessibility Audit

| Check | Tool | Standard |
|-------|------|----------|
| Heading hierarchy | Manual | h1 → h2 → h3, no skips |
| Color contrast | axe, Lighthouse | WCAG AA (4.5:1 text, 3:1 large) |
| Alt text | Manual | All images have descriptive alt |
| Keyboard navigation | Manual | All interactive elements focusable |
| Screen reader | VoiceOver/NVDA | Content reads sensibly |
| ARIA labels | Manual | Interactive elements labeled |
| Focus indicators | Manual | Visible focus state |
| Language attributes | Manual | Code blocks have lang attr |

### 5B: Performance Audit

| Metric | Target | Tool |
|--------|--------|------|
| LCP | < 2.5s | Lighthouse |
| FID | < 100ms | Lighthouse |
| CLS | < 0.1 | Lighthouse |
| Total bundle | < 200KB | Build output |
| Image optimization | WebP, lazy loaded | Manual |

### 5C: Code Quality

| Check | Standard |
|-------|----------|
| No console errors | Zero errors in dev tools |
| No TypeScript errors | `npm run typecheck` passes |
| Linting | `npm run lint` passes |
| Build succeeds | `npm run build` completes |

### Tasks

| Task | Description | Deliverable |
|------|-------------|-------------|
| 5.1 | Run Lighthouse audit | Score report |
| 5.2 | Run accessibility audit | Issue list |
| 5.3 | Test keyboard navigation | Pass/fail |
| 5.4 | Test screen reader | Pass/fail |
| 5.5 | Fix all issues found | Zero issues |

### Success Criteria

- [ ] Lighthouse accessibility score ≥ 95
- [ ] Lighthouse performance score ≥ 90
- [ ] Zero accessibility violations
- [ ] Keyboard navigation works fully
- [ ] Build succeeds with no warnings

### Confidence Definition

**100% confident** when: All automated tools pass, manual testing complete, zero known issues.

---

## Phase 6: User Perspective Review

**Purpose**: Experience the page as a first-time visitor.

### 6A: 5-Second Test

Show page to someone unfamiliar with Motus for 5 seconds, then ask:

1. What does this product do?
2. Who is it for?
3. What's the main benefit?
4. What action should you take?

**Pass**: They can answer all 4 correctly.
**Fail**: Any confusion or wrong answer.

### 6B: Jargon Audit

Read every word on the page. Flag:

| Category | Examples | Action |
|----------|----------|--------|
| **Technical jargon** | tokens, CRUD, UUID, API | Replace or explain |
| **AI jargon** | context window, re-prompting, embeddings | Replace with plain language |
| **Internal terminology** | rx_001, lease_id | Replace with user-friendly terms |
| **Acronyms** | LLM, RAG, OODA | Spell out or remove |

### 6C: Visual Consistency Audit

| Check | What to Look For |
|-------|------------------|
| Color consistency | Same elements same color everywhere |
| Spacing consistency | Same gaps between similar elements |
| Typography consistency | Same text sizes for same purposes |
| Component consistency | Buttons/panels look identical |
| Accent usage | Accent color used consistently (not randomly) |

### 6D: Claims Audit

For every claim on the page:

| Claim | Type | Evidence | Qualified? |
|-------|------|----------|------------|
| "95% fewer tokens" | Quantitative | Benchmark | Must link to proof |
| "Works with Claude, GPT..." | Capability | Test matrix | Must have tested |
| "5 minutes to first receipt" | Time | User testing | Must have timed |

### Tasks

| Task | Description | Deliverable |
|------|-------------|-------------|
| 6.1 | Conduct 5-second test (3+ people) | Test results |
| 6.2 | Complete jargon audit | Jargon list with replacements |
| 6.3 | Complete visual consistency audit | Issue list |
| 6.4 | Complete claims audit | Claims with evidence status |
| 6.5 | Fix all issues found | Zero user-perspective issues |

### Success Criteria

- [ ] 5-second test passes with 3+ people
- [ ] Zero unexplained jargon
- [ ] Zero visual inconsistencies
- [ ] Every claim either has evidence or is qualified/removed

### Confidence Definition

**100% confident** when: Someone who has never heard of Motus understands the page completely on first read.

---

## Phase 7: Credibility Review

**Purpose**: Ensure all claims meet proof standards.

### 7A: Evidence Standards

| Claim Type | Minimum Evidence Required |
|------------|---------------------------|
| Performance (latency) | N ≥ 1,000 samples, p50/p95/p99, reproducible script |
| Reduction (%) | Real tokenizer (tiktoken), before/after comparison, N ≥ 100 |
| Compatibility | Actual test runs with each provider, test logs |
| User metrics | Analytics data with statistical significance |
| Time claims | User testing with N ≥ 10, measured completion times |

### 7B: Evidence Bundle Structure

Each claim needs:

```
/docs/proof/[claim-name]/
├── methodology.md      # How we measured
├── results.json        # Raw data
├── reproduce.sh        # Script to reproduce
└── manifest.json       # Metadata
```

### 7C: Proof Ledger

All claims must be registered:

```json
{
  "claims": [
    {
      "id": "token-reduction-95",
      "claim": "95% fewer tokens",
      "location": "homepage-section-1",
      "evidence_path": "/docs/proof/token-reduction/",
      "status": "verified",
      "last_verified": "2026-01-06",
      "methodology": "tiktoken, N=1000, 4 scenarios"
    }
  ]
}
```

### 7D: Claim Classification

| Status | Meaning | Action |
|--------|---------|--------|
| **Verified** | Evidence meets standards | Can display prominently |
| **Preliminary** | Evidence exists but below standard | Must qualify ("up to", "in testing") |
| **Unverified** | No evidence | Remove or mark as goal |

### Tasks

| Task | Description | Deliverable |
|------|-------------|-------------|
| 7.1 | List all claims on page | Claim inventory |
| 7.2 | Classify each claim | Status per claim |
| 7.3 | Build evidence bundles for verified claims | Evidence bundles |
| 7.4 | Qualify or remove unverified claims | Updated copy |
| 7.5 | Update proof ledger | Ledger file |

### Success Criteria

- [ ] Every quantitative claim has evidence bundle
- [ ] Every claim is in proof ledger
- [ ] No unverified claims displayed as fact
- [ ] Evidence is reproducible by third party

### Confidence Definition

**100% confident** when: A skeptical developer could verify every claim by running the provided scripts.

---

## Phase 8: Pre-Launch

**Purpose**: Final verification before going live.

### 8A: Deployment Checklist

| Check | Status |
|-------|--------|
| Build succeeds locally | |
| Build succeeds in CI | |
| Preview deployment works | |
| All links work | |
| Images load | |
| Fonts load | |
| No console errors | |
| Analytics configured | |
| Meta tags correct | |
| OG image works | |
| Favicon works | |

### 8B: Cross-Browser Testing

| Browser | Version | Status |
|---------|---------|--------|
| Chrome | Latest | |
| Firefox | Latest | |
| Safari | Latest | |
| Edge | Latest | |
| Mobile Safari | Latest | |
| Mobile Chrome | Latest | |

### 8C: Final Review

- [ ] Read entire page out loud
- [ ] Check on mobile device (not emulator)
- [ ] Check in incognito/private mode
- [ ] Have someone unfamiliar navigate the site
- [ ] Verify all CTAs work and go to correct destinations

### Tasks

| Task | Description | Deliverable |
|------|-------------|-------------|
| 8.1 | Complete deployment checklist | All checks pass |
| 8.2 | Complete cross-browser testing | All browsers pass |
| 8.3 | Final read-through | Sign-off |
| 8.4 | Deploy to production | Live site |
| 8.5 | Verify production | Post-deploy check |

### Success Criteria

- [ ] All checklist items pass
- [ ] All browsers work
- [ ] Final review sign-off obtained
- [ ] Production site matches staging exactly

### Confidence Definition

**100% confident** when: You would be comfortable showing this to a potential customer or investor right now.

---

## Phase Summary

| Phase | Purpose | Gate |
|-------|---------|------|
| 0. Foundation | Prerequisites exist | All systems verified |
| 1. Research | Decisions grounded in evidence | Pattern docs complete |
| 2. Information Architecture | Content structured | Outlines approved |
| 3. Visual Design | Layouts defined | Design system compliant |
| 4. Implementation | Code written | Quality gates pass |
| 5. Technical Review | Quality verified | Audits pass |
| 6. User Perspective | Clarity verified | 5-second test passes |
| 7. Credibility | Claims verified | Evidence bundles exist |
| 8. Pre-Launch | Final checks | Deployment succeeds |

---

## When to Use This Process

### Full Process (All Phases)
- New page creation
- Major redesign
- Launch preparation

### Abbreviated Process (Phases 5-8)
- Content updates
- Bug fixes
- Minor changes

### Skip to Phase 6-7
- Copy changes
- Claim updates

---

## Confidence Levels

| Level | Definition | When to Proceed |
|-------|------------|-----------------|
| **100%** | All criteria met, all evidence exists, no doubts | Ship immediately |
| **90%** | Minor issues exist, none blocking | Ship with follow-up tasks |
| **70%** | Significant issues, but core works | Ship to staging only |
| **50%** | Major issues, uncertain about quality | Do not ship, iterate |
| **<50%** | Fundamental problems | Stop, reassess approach |

---

## Anti-Patterns to Avoid

| Anti-Pattern | Why It's Bad | What to Do Instead |
|--------------|--------------|-------------------|
| Skip research | Decisions become arbitrary | Always cite sources |
| Use arbitrary values | Design system breaks down | Only use tokens |
| Ship unverified claims | Credibility destroyed | Build evidence first |
| Test only on desktop | Mobile users suffer | Test mobile first |
| Skip user testing | Jargon accumulates | Always do 5-second test |
| Fix issues ad-hoc | Problems compound | Follow the phases |
| Deploy to localhost | Can't verify production | Always deploy to real environment |

---

*This process ensures every website change is researched, designed, implemented, and verified to Motus standards.*
