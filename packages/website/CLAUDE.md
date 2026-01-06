# Motus Website Guide

This file is the website-specific implementation guide for copy, structure, and audits.
It **derives** from the foundation voice standards:
- `/core/voice/anti-patterns.md` ("Plain language, concrete nouns")
- `/core/voice/ben-voice-core.md` ("Clarity over caution")

If those principles conflict with a page draft, the foundation wins.

---

## Core Principle

**Clarity over cleverness.** Every line must explain what Motus is or how to use it.

---

## Locked Homepage Structure

### Hero (Above Fold)

**Headline:** "What did your agent actually do?"
**Answer:** "Motus knows."

This is the canonical headline. It passes all copy tests:
- **Simple:** 6 words question, 2 word answer
- **Unexpected:** Voices the doubt nobody says out loud
- **Concrete:** "Motus knows" is definitive, not "can help you know"
- **Credible:** Backed by real metrics (434 claims, 1,772 events)
- **Emotional:** Relief from uncertainty
- **Story:** Implies the whole narrative (doubt -> answer -> proof)

**Value Prop:** "Every action logged. Every decision recorded. Every outcome, receipted."

**CTA:** "Get your first receipt" -> /get-started

### Section Structure

1. **The Loop** - Claim. Prove. Release.
   - 3 panels, 3 commands, instant understanding
   - "That's the loop. Every action, receipted."

2. **The Proof** - Real Numbers
   - 434 work claims processed
   - 1,772 audit events logged
   - 106 decisions recorded
   - "Every one immutable. Every one verifiable."

3. **The Receipt** - What You Get
   - Outcome, Evidence, Decisions
   - "One receipt. Full story."

4. **Works With** - Universal compatibility
   - Claude, GPT, Gemini, LangChain, n8n, Local agents

5. **Trust** - Source available. Local first. Yours.

6. **Final CTA** - "Know what your agents did."

---

## Mathematical Design System

All UI/UX derives from phi (golden ratio = 1.618).

### Spacing (Fibonacci)
Already in `tailwind.config.mjs`:
- phi-1: 8px (F6)
- phi-2: 13px (F7)
- phi-3: 21px (F8)
- phi-4: 34px (F9)
- phi-5: 55px (F10)
- phi-6: 89px (F11)
- phi-7: 144px (F12)
- phi-8: 233px (F13)

### Typography Scale
Base: 16px, scale by phi^n
- xs: 10px (16/phi)
- sm: 13px
- base: 16px
- lg: 21px
- xl: 26px
- 2xl: 34px
- 3xl: 42px
- 4xl: 55px
- 5xl: 68px
- 6xl: 89px

### Animation Timing
- fast: 120ms
- base: 200ms (120 * phi)
- slow: 320ms (200 * phi)

---

## Landing Page Framework

Synthesized from Julian Shapiro, Harry Dry, StoryBrand.

### Conversion Formula
`Conversion = Desire - (Labor + Confusion)`
- Maximize desire: Show the outcome, not the process
- Minimize labor: One CTA, clear next step
- Minimize confusion: 5-second comprehension test

### Copy Tests (Harry Dry)
Every headline must pass:
1. **Can I visualize it?** (Concrete image)
2. **Can I falsify it?** (Testable claim)
3. **Can nobody else say it?** (Unique to us)

### Above-Fold Elements
1. Title (5-8 words max)
2. Subtitle (one sentence)
3. Visual (show, don't tell)
4. Social proof (if real)
5. CTA (single, clear action)

---

## Provable Claims Policy

Canonical claims live in `CONTENT-STANDARD.md` and `standards/proof-ledger.json`.
Do not add or restate claims here. The lists below are historical reference only
and must be verified in the proof ledger before use.

### We CAN Claim (Evidence Exists)

**Core API Claims:**
| Claim | Evidence |
|-------|----------|
| "6 API calls" | `docs/proofs/api-calls-count/method.md` |
| "Every action logged" | 1,772+ audit events (immutable, append-only) |
| "Decisions recorded" | 106 decision records in production |
| "Works with Claude, GPT, Gemini" | Session file cache: 45+ sessions indexed |

**Operational Metrics (from coordination.db):**
| Metric | Value | Source |
|--------|-------|--------|
| Total operations tracked | 4,821 | metrics table |
| Work claims processed | 434 | work_compiler.claim_work |
| Policy runs executed | 339 | policy_run operation |
| Decisions recorded | 106 | work_compiler.record_decision |
| Evidence bundles | 14 | work_compiler.record_evidence |
| Sessions indexed | 45 | session_file_cache |
| Change requests tracked | 54 | change_requests table |

**Milestone: Solo OODA Validation (2026-01-02):**
| Metric | Before | After | Delta |
|--------|--------|-------|-------|
| Test failures | 58 | 0 | -58 |
| Tests passing | 1,859 | 1,922 | +63 |
| OODA cycles completed | 0 | 40+ | +40 |
| Evidence log entries | 0 | 40+ | +40 |

Source: `.ai/milestones/2026-01-02-SOLO-OODA-VALIDATION.md`

**Performance Baselines:**
| Operation | Avg (ms) | Calls |
|-----------|----------|-------|
| claim_work | 1.36 | 434 |
| record_decision | 0.51 | 106 |
| get_context | 0.15 | 16 |
| release_work | 1.49 | 18 |

### We CANNOT Claim (No Proof Yet)
- Token reduction percentages (no before/after measurement)
- "X% faster" without documented baseline
- User adoption numbers
- Production deployment counts

### Proof Pack Requirement
Before adding any numeric claim:
1. Create proof bundle in `docs/proof/<claim-id>/`
2. Include `methodology.md`, `results.json`, `reproduce.sh`, and `manifest.json`
3. Link from website copy within one scroll
4. OR reference a verified proof ledger entry

---

## JTBD Framing

- **Job**: "I need to know what my agents did."
- **Obstacle**: "I can't prove it."
- **Outcome**: "I can show receipts and move forward."

Each section should map to at least one of those.

---

## The 5 Cs Checklist

- **Clear**: a new visitor understands in 10 seconds
- **Concrete**: specific nouns, not abstractions
- **Credible**: no claims without proof links
- **Concise**: one idea per sentence
- **Consistent**: same terms across site + README

---

## Copy Audit Process

For each section:
1. **Vision?** Does it explain what becomes possible?
2. **Usage?** Does it show how to do it now?
3. **Trust?** Does it remove doubt?

If it does none of those, cut it.

---

## Proof Discipline

- No statistics without a proof link.
- If a feature is not shipped, mark it **Building** or **Future**.
- "Receipts" is the canonical metaphor. Avoid substitutes unless approved.

---

## Review Process

Website changes follow a multi-phase review process with gates:

- **Full process**: `REVIEW-PROCESS.md` (8 phases, validation modes, artifact chain)
- **Writing gates**: `CONTENT-STANDARD.md` (short, enforceable pre-writing checks)
- **Claims registry**: `standards/proof-ledger.json` (all claims must be registered)
- **Terminology**: `standards/terminology.json` (approved/banned terms)
- **Benchmark spec**: `CODEX-BENCHMARK-HANDOFF.md` (homepage proof environment)

Sign-offs are recorded in `artifacts/sign-offs/`.

---

## Scope Rules

- Website copy lives in `packages/website/**`.
- Canonical messaging lives in `packages/website/src/data/messaging.json`.
- Generated copy must stay in sync with messaging automation.
