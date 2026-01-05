# Motus Website Guide

This file is the website-specific implementation guide for copy, structure, and audits.
It **derives** from the foundation voice standards:
- `/core/voice/anti-patterns.md` ("Plain language, concrete nouns")
- `/core/voice/ben-voice-core.md` ("Clarity over caution")

If those principles conflict with a page draft, the foundation wins.

---

## Core Principle

**Clarity over cleverness.** Every line must explain what Motus is or how to use it.

## JTBD Framing

- **Job**: “I need to know what my agents did.”
- **Obstacle**: “I can’t prove it.”
- **Outcome**: “I can show receipts and move forward.”

Each section should map to at least one of those.

## Headline + Clarifier Pattern

- **Headline** = the idea in 5–8 words.
- **Clarifier** = how it works, in one sentence.

Example:
- **Headline**: “Agents do the work.”
- **Clarifier**: “Motus keeps the receipts.”

## No Jargon Without Context

If a term is unfamiliar, define it in the same line.
Bad: “Outcome/Mechanism”
Good: “Claim work. Attach proof. Ship a receipt.”

## The 5 Cs Checklist

- **Clear**: a new visitor understands in 10 seconds
- **Concrete**: specific nouns, not abstractions
- **Credible**: no claims without proof links
- **Concise**: one idea per sentence
- **Consistent**: same terms across site + README

## Copy Audit Process

For each section:
1. **Vision?** Does it explain what becomes possible?
2. **Usage?** Does it show how to do it now?
3. **Trust?** Does it remove doubt?

If it does none of those, cut it.

## Proof Discipline

- No statistics without a proof link.
- If a feature is not shipped, mark it **Building** or **Future**.
- “Receipts” is the canonical metaphor. Avoid substitutes unless approved.

## Scope Rules

- Website copy lives in `packages/website/**`.
- Canonical messaging lives in `packages/cli/docs/website/messaging.yaml`.
- Generated copy must stay in sync with messaging automation.

