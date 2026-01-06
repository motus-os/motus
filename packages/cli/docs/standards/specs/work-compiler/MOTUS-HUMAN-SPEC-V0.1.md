# MOTUS-HUMAN-SPEC-V0.1

**Human Spec Version:** 0.1.0  
**Date:** 2025-12-24  
**Status:** Implementation Contract (normative “MUST/SHOULD/MAY” language)  
**Depends on:** `MOTUS-SPEC-V0.1` (computer-side kernel: CJ-0.1, PROOF-0.1, FSM-0.1, ENF-0.1)

Motus is “scope enforcement and proof capture” for agents. The computer-side spec makes work deterministic and auditable. This document formalizes the **human-side**: deterministic, verifiable structures that encode human wisdom:

- **EMPATHY-0.1** — understood what the user actually needed
- **PERSPECTIVE-0.1** — considered multiple viewpoints
- **TRUTH-0.1** — claims are grounded and honestly represented
- **PURPOSE-0.1** — work serves a meaningful goal
- **HUMILITY-0.1** — limitations and uncertainty are acknowledged
- **FITNESS-0.1** — output is fit-for-purpose (not just “done”)

These are implemented as **deterministic check modules** that consume structured evidence (JSON files under `evidence/human/**`) and emit `CheckResult` entries (and optional additional fields) that are:
- included in the receipt (CJ-0.1),
- covered by `verification_root` / `evidence_root`,
- validated by `verify_bundle` as part of PROOF-0.1.

> **Design constraint:** human-side checks MUST be **integer-only**, scored in **permille** (0..1000), and MUST be verifiable by an independent implementation without re-executing agent reasoning.

---

## Table of contents

0. Scope and integration summary  
1. Common types and helper algorithms  
2. EMPATHY-0.1  
3. PURPOSE-0.1  
4. HUMILITY-0.1  
5. PERSPECTIVE-0.1  
6. TRUTH-0.1  
7. FITNESS-0.1  
8. DECIDE pre-flight integration (HUMAN-PREFLIGHT-0.1)  
9. VERIFY integration and ordering  
10. Receipt + evidence formats  
11. verify_bundle extensions and failure codes  
12. Testing and benchmarking (human-side golden fixtures)  
13. Default thresholds and calibration guidance  
Appendix A. JSON schema sketches (human evidence files)  
Appendix B. Example fixtures (inputs + expected scores/failures)

---

# 0. Scope and integration summary

## 0.1 Where human-side checks run in the Work Compiler

Motus Work Compiler phases: `Observe → Orient → Decide → Act → Verify → Lock`.

Human-side checks integrate at two primary points:

1. **DECIDE pre-flight (MUST for non-trivial lock levels)**  
   - Runs: `EMPATHY-0.1`, `PURPOSE-0.1`, `HUMILITY-0.1`  
   - Outcome: may force backtrack to `ORIENT` / `OBSERVE`, or require HITL, before any irreversible ACT occurs.

2. **VERIFY (MUST before LOCK when required by policy/lock level)**  
   - Runs: `TRUTH-0.1`, `PERSPECTIVE-0.1`, `FITNESS-0.1`  
   - Outcome: may force backtrack to `OBSERVE` (insufficient grounding), spawn Agent Council (perspective deficit), require HITL (fitness subjective), or fail-lock.

## 0.2 Mapping into existing verification tiers (v0.1)

`MOTUS-SPEC-V0.1` defines `VerificationLevel ∈ {Syntactic, Semantic, Regression, Acceptance}`.

To avoid breaking core types in v0.1, human-side modules are represented as **named checks** (string `check_id`) under existing levels:

- Semantic-level checks:
  - `EMPATHY-0.1`
  - `PURPOSE-0.1`
  - `HUMILITY-0.1`
  - `PERSPECTIVE-0.1`
  - `TRUTH-0.1`  *(this is the “Grounding” tier conceptually)*

- Acceptance-level checks:
  - `FITNESS-0.1` *(this is the “Fit-for-purpose” tier conceptually)*

> Implementations SHOULD execute `TRUTH-0.1` after basic semantic checks but before acceptance tests, and SHOULD execute `FITNESS-0.1` after acceptance tests.

## 0.3 Human evidence as first-class, hashed inputs

Each human-side module consumes a required evidence file:

- `evidence/human/empathy_report.json`
- `evidence/human/purpose_report.json`
- `evidence/human/humility_report.json`
- `evidence/human/perspective_report.json`
- `evidence/human/claimset.json` (TRUTH)
- `evidence/human/fitness_report.json`

These files are included in:
- `manifest.files` (sha256),
- `evidence_root` (Merkle root),
- `proof_digest` (via PROOF-0.1).

## 0.4 New signals for strategy suggestion

Human-side modules MAY emit signals (with permille confidence) to the Strategy Library in ORIENT/DECIDE, including:

- `multi_perspective_decision_needed`
- `high_stakes_messaging_or_positioning`
- `architectural_decision_with_user_impact`
- `need_fresh_eyes_on_established_direction`
- `purpose_unclear`
- `grounding_insufficient`
- `fitness_subjective`

These are intended to trigger strategies like `STRAT-009 Agent Council` and “Devil’s Advocate”.

---

# 1. Common types and helper algorithms

This section defines shared types and deterministic text / scoring utilities.

## 1.1 Primitive types

Re-use from `MOTUS-SPEC-V0.1`:

- `Permille(u16)` in `[0..=1000]`
- `Millis(u64)`
- `Hash256([u8;32])`
- `LoopId`, `EventId`

## 1.2 Human check identifiers and results

```rust
use serde::{Serialize, Deserialize};

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub enum HumanCheckId {
    Empathy,      // EMPATHY-0.1
    Perspective,  // PERSPECTIVE-0.1
    Truth,        // TRUTH-0.1
    Purpose,      // PURPOSE-0.1
    Humility,     // HUMILITY-0.1
    Fitness,      // FITNESS-0.1
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct HumanCheckResult {
    pub check_id: String,           // e.g., "EMPATHY-0.1"
    pub score: Permille,            // computed deterministically
    pub threshold: Permille,        // policy-derived
    pub passed: bool,               // score >= threshold AND no hard-fail conditions
    pub evidence_path: String,      // evidence/human/*.json
    pub flags: Vec<String>,         // e.g., ["FIT_SUBJECTIVE"]
    pub reasons: Vec<String>,       // deterministic short strings
}
```

## 1.3 Human evidence reference types

TRUTH-0.1 needs explicit source references.

```rust
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub enum SourceKind {
    LensItem,      // references a lens item hash/id
    EvidenceFile,  // references evidence file within bundle
    Artifact,      // references artifact path/sha
    ExternalSnap,  // external snapshot captured into evidence (still file-based)
    UserAssertion, // user-provided, not independently verifiable
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct SourceRef {
    pub kind: SourceKind,
    pub ref_id: String,     // LensItem: lens item `uri`; EvidenceFile/ExternalSnap: relative evidence path; Artifact: artifact path; UserAssertion: label
    pub sha256: String,     // sha256 of referenced bytes (or excerpt bytes)
    pub excerpt: Option<Excerpt>, // optional excerpt bounds for fidelity checks
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct Excerpt {
    pub start: u32, // byte offset
    pub end: u32,   // byte offset (exclusive)
}
```

## 1.4 Tokenization and anchors (deterministic)

### Tokenization (TOK-0.1)

Define a deterministic tokenizer:

- lowercase ASCII (non-ASCII kept but lowercased via Unicode simple fold if available; v0.1 MAY restrict to ASCII-only for simplicity)
- split on any non-alphanumeric character
- drop tokens with length < 3
- drop stopwords from a fixed list `STOPWORDS_0_1`

`STOPWORDS_0_1` MUST be a fixed, versioned set in code.

`STOPWORDS_0_1` (exact, v0.1):

```text
a
about
above
after
again
all
also
am
an
and
any
are
as
at
be
because
been
before
being
below
between
both
but
by
can
could
did
do
does
doing
down
during
each
few
for
from
further
had
has
have
having
he
her
here
hers
herself
him
himself
his
how
i
if
in
into
is
it
its
itself
just
me
more
most
my
myself
no
nor
not
now
of
off
on
once
only
or
other
our
ours
ourselves
out
over
own
same
she
should
so
some
such
than
that
the
their
theirs
them
themselves
then
there
these
they
this
those
through
to
too
under
until
up
very
was
we
were
what
when
where
which
while
who
whom
why
with
would
you
your
yours
yourself
yourselves
```

```rust
pub fn tokenize_tok_0_1(s: &str) -> Vec<String>;
```

### Anchor extraction (ANCHOR-0.1)

Compute an anchor token set from:
- `intent.description`
- optional “key constraints” strings (if your Work Compiler stores them)

Algorithm:
1. tokens = tokenize(intent.description)
2. count frequency
3. keep top `N=12` tokens by (freq desc, token lex asc)
4. store as `BTreeSet<String>`

```rust
use std::collections::BTreeSet;

pub fn anchor_tokens(intent_description: &str) -> BTreeSet<String>;
```

### Overlap score (permille)

For token sets `A` (anchors) and `T` (text tokens):

\[
overlap(A,T) = \left\lfloor 1000 \cdot \frac{|A \cap T|}{\max(1, |A|)} \right\rfloor
\]

```rust
pub fn overlap_permille(anchors: &BTreeSet<String>, text: &str) -> Permille;
```

### Jaccard similarity (permille)

\[
jaccard(A,B) = \left\lfloor 1000 \cdot \frac{|A \cap B|}{\max(1, |A \cup B|)} \right\rfloor
\]

```rust
pub fn jaccard_permille(a: &BTreeSet<String>, b: &BTreeSet<String>) -> Permille;
```

---

# 2. EMPATHY-0.1 — User Understanding Verification

## 2.1 Purpose

Verify the agent understood what was actually needed (audience, expectations, trust), not just literal instructions.

## 2.2 Evidence format

Required evidence file: `evidence/human/empathy_report.json`

```rust
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct EmpathyReport {
    pub version: String,         // "EMPATHY-0.1"
    pub recipient: String,       // Who will receive this output?
    pub prior_knowledge: String, // What do they already know?
    pub needs: String,           // What do they need to understand/feel?
    pub confusion_risks: String, // What might confuse or frustrate them?
    pub trust_builders: String,  // What would make them trust this?
}
```

All fields MUST be non-empty strings after trimming.

## 2.3 Scoring (integer-only, permille)

Let anchors = `anchor_tokens(intent.description)`.

### Subscores

1) **Coverage**  
All 5 fields required:

\[
coverage = \left\lfloor 1000 \cdot \frac{present}{5} \right\rfloor
\]

2) **Alignment**  
Compute overlap for each field and average:

\[
alignment = \left\lfloor \frac{\sum_{f \in Fields} overlap(anchors, f)}{5} \right\rfloor
\]

3) **Specificity**  
Let `tok_count` = total tokens across all fields.  
Let `marker_count` = count of “concrete markers” across all fields:
- digits `0-9`
- path-ish characters: `'/'`, `'.'`, `':'`, `'_'`, `'-'`

Define:
- `len_score = min(1000, 20 * tok_count)` (50 tokens → 1000)
- `mark_score = min(1000, 200 * marker_count)` (5 markers → 1000)
- `specificity = floor((len_score + mark_score) / 2)`

4) **Trust**  
Let `trust_tokens` be a fixed set:  
`{"evidence","receipt","verify","source","tests","assumptions","limitations","citations"}`.

Let `k` be the count of trust_tokens present as substrings in `trust_builders` (case-insensitive).

- if `k >= 2` → 1000
- if `k == 1` → 700
- else → 0

### Total score

Weights (sum 1000):
- coverage 400
- alignment 300
- specificity 200
- trust 100

\[
empathy = \left\lfloor \frac{400\cdot coverage + 300\cdot alignment + 200\cdot specificity + 100\cdot trust}{1000} \right\rfloor
\]

## 2.4 Thresholds (default)

Default per lock level:

| LockLevel | Threshold |
|----------|-----------|
| Draft    | 400 |
| Staged   | 600 |
| Committed| 750 |
| Published| 850 |
| Immutable| 900 |

(Policy MAY override; see Section 13.)

## 2.5 Transition rules

EMPATHY-0.1 is evaluated in **DECIDE pre-flight**.

- If `empathy < threshold`:
  - Default transition: `Backtrack(Orient, "EMPATHY_LOW")`
  - If lock level ≥ `Committed` and backtrack count ≥ 1: `Halt(requires_human=true, reason="EMPATHY_LOW_REQUIRES_CLARIFICATION")`

## 2.6 Failure codes (human-side)

- `EMPATHY_MISSING_EVIDENCE`
- `EMPATHY_MISSING_FIELDS`
- `EMPATHY_LOW_SCORE`

---

# 3. PURPOSE-0.1 — Meaningful Work Verification

## 3.1 Purpose

Verify the work serves a meaningful goal and stakes are understood.

## 3.2 Evidence format

Required evidence file: `evidence/human/purpose_report.json`

```rust
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct PurposeReport {
    pub version: String,          // "PURPOSE-0.1"
    pub why_it_matters: String,   // Why does this matter?
    pub problem_solved: String,   // What problem does this solve?
    pub beneficiaries: String,    // Who benefits?
    pub cost_of_wrong: String,    // What's the cost of getting this wrong?
    pub success_criteria: Option<Vec<String>>, // Optional explicit criteria
    pub devils_advocate: Option<String>,       // Optional counterargument
}
```

## 3.3 Scoring

Anchors as in EMPATHY.

### Subscores

1) Coverage over required 4 core fields:

\[
coverage = \left\lfloor 1000 \cdot \frac{present}{4} \right\rfloor
\]

2) Alignment: average overlap over the 4 core fields.

3) Stakes (cost-of-wrong strength)

Let `stakes_tokens` be fixed:  
`{"break","risk","loss","security","compliance","privacy","downtime","production","data","money","reputation"}`.

Let `k` = count of tokens present in `cost_of_wrong` (substring, case-insensitive), capped at 5.

\[
stakes = min(1000, 200 \cdot k)
\]

4) Devil’s Advocate presence

- If `devils_advocate` is present and token count ≥ 20 → 1000
- Else if absent → 500 (allowed in low lock levels)
- Else → 700 (short but present)

### Total

Weights:
- coverage 350
- alignment 250
- stakes 250
- devils_advocate 150

\[
purpose = \left\lfloor \frac{350c + 250a + 250s + 150d}{1000} \right\rfloor
\]

## 3.4 Thresholds (default)

| LockLevel | Threshold |
|----------|-----------|
| Draft    | 400 |
| Staged   | 600 |
| Committed| 750 |
| Published| 800 |
| Immutable| 850 |

## 3.5 Transition rules

PURPOSE-0.1 is evaluated in DECIDE pre-flight.

- If `purpose < threshold`:
  - Default: `Backtrack(Orient, "PURPOSE_WEAK")`
  - If lock level ≥ `Published`: recommend strategy `Devil’s Advocate` or `Agent Council`.

## 3.6 Failure codes

- `PURPOSE_MISSING_EVIDENCE`
- `PURPOSE_MISSING_FIELDS`
- `PURPOSE_LOW_SCORE`

---

# 4. HUMILITY-0.1 — Limitation Acknowledgment

## 4.1 Purpose

Verify the agent acknowledges uncertainty, assumptions, and recommends human double-checks where appropriate.

## 4.2 Evidence format

Required evidence file: `evidence/human/humility_report.json`

```rust
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct HumilityReport {
    pub version: String,              // "HUMILITY-0.1"
    pub assumptions: Vec<String>,      // explicit assumptions
    pub uncertainties: Vec<String>,    // explicit unknowns
    pub uncertainty_permille: Permille,// declared uncertainty (0=very sure, 1000=very unsure)
    pub human_double_checks: Vec<String>, // what a human should double-check
}
```

Constraints:
- `assumptions.len() >= 1` for lock level ≥ `Committed`
- `uncertainties.len() >= 1` for lock level ≥ `Committed`
- `human_double_checks.len() >= 1` for lock level ≥ `Committed`

## 4.3 Scoring

### Subscores

1) Coverage:
- For lock level < Committed: require evidence present; lists may be empty.
- For lock level ≥ Committed: require at least 1 item in each list.

Compute `present_fields` = number of fields satisfying their requirement.

\[
coverage = \left\lfloor 1000 \cdot \frac{present\_fields}{4} \right\rfloor
\]

2) Assumption richness:
Let `a = min(4, assumptions.len())`.  
`assumption_score = 250 * a` (cap 1000)

3) Uncertainty richness:
Let `u = min(4, uncertainties.len())`.  
`uncertainty_list_score = 250 * u`

4) Actionability:
Let `h = min(4, human_double_checks.len())`.  
`actionability = 250 * h`

5) Calibration (understatement penalty)

Define a **structural uncertainty floor** `u_min` from lens quality:

Let `L = receipt.lens.quality.aggregate` (permille).

\[
u_{min} = \max(200, 1000 - L)
\]

Rationale: if the lens is weak (low aggregate), the agent MUST not claim extreme certainty.

Let `decl = humility.uncertainty_permille`.

If `decl >= u_min` → `calibration = 1000`.  
Else let `delta = u_min - decl` (positive). Define:

\[
calibration = max(0, 1000 - 2 \cdot delta)
\]

(So being 100 permille too confident reduces score by 200.)

### Total

Weights:
- coverage 300
- assumption_score 150
- uncertainty_list_score 150
- actionability 200
- calibration 200

\[
humility = \left\lfloor \frac{300c + 150a + 150u + 200x + 200k}{1000} \right\rfloor
\]

## 4.4 Thresholds (default)

| LockLevel | Threshold |
|----------|-----------|
| Draft    | 300 |
| Staged   | 500 |
| Committed| 700 |
| Published| 750 |
| Immutable| 800 |

## 4.5 HITL escalation rule

If lock level ≥ `Committed` and either:
- `uncertainty_permille ≥ 700`, OR
- `humility < threshold`

Then Motus MUST set `requires_human=true` before LOCK (policy-driven).

## 4.6 Failure codes

- `HUMILITY_MISSING_EVIDENCE`
- `HUMILITY_INSUFFICIENT_DISCLOSURE`
- `HUMILITY_UNCERTAINTY_UNDERSTATED`
- `HUMILITY_LOW_SCORE`

---

# 5. PERSPECTIVE-0.1 — Multi-Viewpoint Verification

## 5.1 Purpose

Verify multiple perspectives were considered (skeptic/novice/expert/outsider), and that dissent is surfaced, not suppressed.

## 5.2 Evidence format

Required evidence file: `evidence/human/perspective_report.json`

```rust
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub enum PerspectiveRole {
    Skeptic,
    Novice,
    Expert,
    Outsider,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub enum Severity {
    Blocker,
    Strong,
    Noted,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct PerspectiveEntry {
    pub role: PerspectiveRole,
    pub points: Vec<String>,          // bullet points
    pub severity: Vec<Severity>,      // same length as points (per-point rating)
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct PerspectiveReport {
    pub version: String,             // "PERSPECTIVE-0.1"
    pub perspectives: Vec<PerspectiveEntry>,
    pub synthesis: Option<String>,   // optional: agreements + tensions + recommendation
    pub council_artifacts: Option<Vec<String>>, // optional file paths if Agent Council used
}
```

## 5.3 Required roles by lock level

| LockLevel | Required roles |
|----------|----------------|
| Draft    | ≥1 (any) |
| Staged   | ≥2 including Skeptic |
| Committed| ≥3 including Skeptic and Novice |
| Published| 4 (Skeptic, Novice, Expert, Outsider) |
| Immutable| 4 + synthesis required |

## 5.4 Scoring

Let `R` be the set of roles present. Let `R_req` required roles.

### Subscores

1) Coverage:

\[
coverage = \left\lfloor 1000 \cdot \frac{|R \cap R_{req}|}{|R_{req}|} \right\rfloor
\]

2) Depth:
For each required role present, define `depth_role = min(1000, 250 * min(4, points.len()))`.  
Depth = average over required roles present (if none, 0).

3) Distinctness:
Compute token set for each role’s concatenated text. For all pairs among required roles present, compute `jaccard`.  
Let `sim_avg` = average similarity permille.  
Define:

\[
distinctness = 1000 - sim_{avg}
\]

4) Tension surfacing:
Let `S` = number of points with severity Blocker or Strong across skeptic+expert roles.  
Define `tension = min(1000, 250 * min(4, S))`.

5) Synthesis:
If lock level ≥ Immutable, synthesis required.  
Score:
- if synthesis present and token count ≥ 50 → 1000
- if synthesis present but short → 700
- if absent → 0 (or 500 if not required by lock level)

### Total

Weights:
- coverage 350
- depth 200
- distinctness 150
- tension 150
- synthesis 150

\[
perspective = \left\lfloor \frac{350c + 200d + 150q + 150t + 150s}{1000} \right\rfloor
\]

## 5.5 Agent Council trigger (STRAT-009 integration)

Motus SHOULD suggest or require `STRAT-009 Agent Council` when:

- lock level ≥ `Published`, OR
- `perspective < threshold` after first attempt, OR
- risk_permille ≥ 700, OR
- the decision affects multiple stakeholders (signal `multi_perspective_decision_needed` ≥ 800)

When Agent Council is used, `council_artifacts` MUST reference deliberation files (stored in evidence), and `synthesis` SHOULD summarize dissent.

## 5.6 Thresholds (default)

| LockLevel | Threshold |
|----------|-----------|
| Draft    | 300 |
| Staged   | 550 |
| Committed| 700 |
| Published| 800 |
| Immutable| 850 |

## 5.7 Transition rules

Evaluated in VERIFY. If below threshold:

- If lock level < Published: `Backtrack(Orient, "PERSPECTIVE_INSUFFICIENT")`
- If lock level ≥ Published: spawn Agent Council child loop(s) (strategy) and re-run PERSPECTIVE check after join.
- If still below threshold: `Halt(requires_human=true, reason="PERSPECTIVE_DEFICIT")`

## 5.8 Failure codes

- `PERSPECTIVE_MISSING_EVIDENCE`
- `PERSPECTIVE_INSUFFICIENT_ROLES`
- `PERSPECTIVE_LOW_SCORE`
- `PERSPECTIVE_COUNCIL_REQUIRED`

---

# 6. TRUTH-0.1 — Grounding Verification

## 6.1 Purpose

Verify claims are traceable to real sources, confidence is honest, and (where feasible) fidelity is mechanically checkable.

## 6.2 Evidence formats

Required evidence file: `evidence/human/claimset.json`

```rust
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub enum ClaimType {
    Fact,
    Quote,
    Numeric,
    Procedure,
    FilePath,
    ApiBehavior,
    Policy,
    Opinion,
    Assumption,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct Claim {
    pub claim_id: String,      // unique
    pub claim_type: ClaimType,
    pub statement: String,     // the claim in plain language
    pub confidence: Permille,  // declared confidence
    pub sources: Vec<SourceRef>,
    pub quote_text: Option<String>,   // required for Quote
    pub numeric_literal: Option<String>, // recommended for Numeric (e.g., "0.1.0", "128")
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct ClaimSet {
    pub version: String,      // "TRUTH-0.1"
    pub claims: Vec<Claim>,
    pub coverage_declared: Permille,  // claimed coverage of output statements
}
```

`coverage_declared` exists because extracting “all claims from arbitrary prose” is not reliably deterministic. v0.1 requires explicit claim annotation.

## 6.3 Deterministic source verification

A `SourceRef` is valid iff:
- it references an existing lens item / evidence file / artifact file (depending on kind), and
- the sha256 matches the referenced bytes (or referenced excerpt bytes).

### Reliability mapping (REL-0.1)

Define a deterministic reliability score `rel(source)`.

For `SourceKind::LensItem`, the verifier MUST look up the referenced lens item in `receipt.lens.items`
(by `uri == ref_id` and `sha256` match) and use its `provenance` field.

| SourceKind | Condition | rel |
|---|---|---|
| LensItem | lens_item.provenance == `"fs"` | 900 |
| LensItem | lens_item.provenance == `"receipt"` | 850 |
| LensItem | lens_item.provenance == `"network"` | 800 |
| LensItem | lens_item.provenance == `"user"` | 600 |
| EvidenceFile | always | 800 |
| Artifact | always | 850 |
| ExternalSnap | always (captured into evidence) | 800 |
| UserAssertion | always | 600 |
| Any | unknown/other | 400 |

(Implementations MUST document their classification function and keep it stable.)

## 6.4 Fidelity checks (mechanical)

Fidelity is a per-claim score:

- Quote:
  - `quote_text` MUST be present and MUST appear as a byte substring of at least one cited source excerpt or full source bytes.
  - If not found → hard fail `TRUTH_QUOTE_NOT_FOUND` and fidelity=0.
  - If found → fidelity=1000.

- FilePath:
  - statement MUST contain a path token; path MUST exist in artifacts or lens files list.
  - If missing → hard fail `TRUTH_PATH_NOT_FOUND`.

- Numeric:
  - `numeric_literal` SHOULD appear as substring in at least one cited source excerpt or bytes.
  - If not found → fidelity=500 (soft penalty), unless lock level ≥ Published (then hard fail).

- Other types:
  - If at least one valid source exists → fidelity=700
  - Else fidelity=0

## 6.5 Confidence calibration (CAL-0.1)

Hard rule:

- Any claim with `sources.len()==0` MUST:
  - have `claim_type == Assumption`, AND
  - `confidence <= 300`.

Otherwise: hard fail `TRUTH_UNCALIBRATED_CONFIDENCE`.

## 6.6 Scoring

Let `N = claims.len()`.

### Subscores

1) Claim coverage (sources present):

Let `n_src = count(claim where valid_sources >= 1)`.

\[
coverage = \left\lfloor 1000 \cdot \frac{n_{src}}{\max(1,N)} \right\rfloor
\]

2) Provenance:

For each claim, take `rel_max` = max reliability among its valid sources (or 0 if none).  
Provenance is average:

\[
provenance = \left\lfloor \frac{\sum rel_{max}}{\max(1,N)} \right\rfloor
\]

3) Fidelity:

Average per-claim fidelity:

\[
fidelity = \left\lfloor \frac{\sum fidelity_i}{\max(1,N)} \right\rfloor
\]

4) Calibration:

- If any hard calibration violation → hard fail, score=0, passed=false.
- Else `calibration = 1000`.

### Total

Weights:
- coverage 400
- provenance 300
- fidelity 250
- calibration 50

\[
truth = \left\lfloor \frac{400c + 300p + 250f + 50k}{1000} \right\rfloor
\]

Additionally, enforce:
- `coverage_declared >= 700` for lock level ≥ Committed (else fail `TRUTH_COVERAGE_TOO_LOW`)

## 6.7 Thresholds (default)

| LockLevel | Threshold |
|----------|-----------|
| Draft    | 300 |
| Staged   | 600 |
| Committed| 750 |
| Published| 850 |
| Immutable| 900 |

## 6.8 Transition rules

TRUTH-0.1 is evaluated in VERIFY.

- If a hard fail occurs (missing sources, quote not found, uncalibrated confidence):
  - `Backtrack(Observe, "GROUNDING_FAILED")` (gather better sources)
- If `truth < threshold`:
  - `Backtrack(Observe, "GROUNDING_LOW")`
- If repeated twice and lock level ≥ Committed:
  - `Halt(requires_human=true, reason="GROUNDING_STUCK")`

## 6.9 Failure codes

- `TRUTH_CLAIMSET_MISSING`
- `TRUTH_SOURCE_MISSING`
- `TRUTH_SOURCE_HASH_MISMATCH`
- `TRUTH_QUOTE_NOT_FOUND`
- `TRUTH_PATH_NOT_FOUND`
- `TRUTH_NUMERIC_NOT_FOUND`
- `TRUTH_UNCALIBRATED_CONFIDENCE`
- `TRUTH_COVERAGE_TOO_LOW`
- `TRUTH_LOW_SCORE`

---

# 7. FITNESS-0.1 — Fit-for-Purpose Verification

## 7.1 Purpose

Verify the output is fit for its intended purpose (context-appropriate, usable, aligned with actual need), not merely “technically correct.”

## 7.2 Evidence format

Required evidence file: `evidence/human/fitness_report.json`

```rust
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub enum FitnessCriterionKind {
    Deterministic,   // checked mechanically (tests, lint, schema, etc.)
    HumanJudgment,   // requires human approval (subjective)
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct FitnessCriterion {
    pub criterion_id: String,
    pub description: String,
    pub kind: FitnessCriterionKind,
    pub evidence: Option<String>, // path to evidence or check output
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct FitnessReport {
    pub version: String,          // "FITNESS-0.1"
    pub criteria: Vec<FitnessCriterion>,
    pub context_notes: Option<String>, // optional context-fit reasoning
    pub subjective_flags: Vec<String>, // e.g., ["tone","brand","legal"]
}
```

## 7.3 Scoring

Let `M = criteria.len()`.

### Deterministic evaluation model (v0.1)

For each criterion:
- If `kind == Deterministic`, it is considered “checked” iff:
  - `evidence` is present and references an evidence file that exists in the bundle.
  - (Optionally) the evidence file content is parseable and indicates pass (your verifier can implement per-check parsing).
- If `kind == HumanJudgment`, it is “checked” only if a human approval artifact exists (see Section 10.4).

In v0.1, FITNESS scoring is based on structural completeness + evidence presence. (Content-level “good taste” remains human-audited via HumanJudgment criteria.)

### Subscores

1) Coverage:

Let `m_checked` = number of criteria with required evidence present (and approvals for HumanJudgment).

\[
coverage = \left\lfloor 1000 \cdot \frac{m_{checked}}{\max(1,M)} \right\rfloor
\]

2) Alignment:
Compute overlap between anchors and `context_notes` (if present), else 500.

3) Subjectivity penalty:
If `subjective_flags` non-empty:
- subjectivity = 700 (soft penalty)
Else subjectivity = 1000.

### Total

Weights:
- coverage 600
- alignment 200
- subjectivity 200

\[
fitness = \left\lfloor \frac{600c + 200a + 200s}{1000} \right\rfloor
\]

## 7.4 Thresholds (default)

| LockLevel | Threshold |
|----------|-----------|
| Draft    | 300 |
| Staged   | 600 |
| Committed| 750 |
| Published| 850 |
| Immutable| 900 |

## 7.5 Subjective fitness rule (HITL)

If lock level ≥ `Committed` and any of:
- there exists a `HumanJudgment` criterion, OR
- `subjective_flags.len() > 0`

Then Motus MUST:
- add flag `FIT_SUBJECTIVE`
- require human checkpoint before LOCK.

## 7.6 Failure codes

- `FITNESS_MISSING_EVIDENCE`
- `FITNESS_CRITERIA_EMPTY`
- `FITNESS_INCOMPLETE`
- `FITNESS_SUBJECTIVE_REQUIRES_HUMAN`
- `FITNESS_LOW_SCORE`

---

# 8. DECIDE pre-flight integration (HUMAN-PREFLIGHT-0.1)

This section defines the deterministic algorithm used during DECIDE.

## 8.1 Algorithm contract

**Signature (conceptual):**

```rust
pub fn decide_preflight_human(
    intent_description: &str,
    lens_quality_aggregate: Permille,
    lock_level: LockLevel,
    policy: &dyn Policy,
    evidence_reader: &dyn EvidenceReader,
) -> Vec<HumanCheckResult>;
```

Where `EvidenceReader` can load `evidence/human/*.json` bytes.

## 8.2 Execution order

In DECIDE pre-flight, execute in this order:

1) EMPATHY-0.1
2) PURPOSE-0.1
3) HUMILITY-0.1

(Reason: if the agent doesn’t understand the user/purpose and can’t admit uncertainty, the plan is not ready.)

## 8.3 Transition rule

Let `required_checks` and thresholds be derived from policy + lock level.

If any required check hard-fails or scores below threshold:
- Default: `Backtrack(Orient, "HUMAN_PREFLIGHT_FAIL:<check>")`
- If lock level ≥ Committed and this is the 2nd attempt:
  - `Halt(requires_human=true, reason="HUMAN_PREFLIGHT_STUCK:<check>")`

Additionally, if HUMILITY triggers HITL rule, set `requires_human=true` even if other checks pass.

---

# 9. VERIFY integration and ordering

## 9.1 Execution order (recommended)

Within VERIFY, run:

1) TRUTH-0.1 (grounding)
2) PERSPECTIVE-0.1 (multi-viewpoint)
3) FITNESS-0.1 (fit-for-purpose)

Rationale:
- Grounding first: avoid debating perspectives around ungrounded claims.
- Fitness last: it consumes the verified outputs and their checks.

## 9.2 Mapping into `CheckResult`

For each human module, append a `CheckResult`:

- Semantic:
  - `check_id` = `"TRUTH-0.1"` / `"PERSPECTIVE-0.1"` / etc.
- Acceptance:
  - `check_id` = `"FITNESS-0.1"`

`passed` MUST be computed as:

- `passed = (score >= threshold) AND (no hard-fail codes)`

Evidence path is stored in `evidence` field.

---

# 10. Receipt + evidence formats

## 10.1 Receipt integration (recommended extension)

Add optional `human` block to the receipt.

```rust
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct HumanBlock {
    pub version: String, // "HUMAN-0.1"
    pub results: Vec<HumanCheckResult>,
}
```

Receipts SHOULD include this block when any human checks are performed or required.

Because receipts are hashed (receipt_hash) and included in proof_digest, this makes human-check outcomes tamper-evident.

## 10.2 Evidence directory layout

Recommended:

```
evidence/
  human/
    empathy_report.json
    purpose_report.json
    humility_report.json
    perspective_report.json
    claimset.json
    fitness_report.json
    approvals/
      fitness_human_approval.json   (if needed)
```

## 10.3 Human approval artifact (for subjective fitness)

When a human approves a subjective criterion, store:

`evidence/human/approvals/fitness_human_approval.json`

```rust
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct HumanApproval {
    pub version: String,         // "HUMAN-APPROVAL-0.1"
    pub approved_by: String,     // user id / name (free text)
    pub approved_at_utc: String,
    pub scope: String,           // e.g. "FITNESS-0.1"
    pub note: Option<String>,
}
```

The verifier checks existence + hashing; authenticity signing is a v0.2 extension.

---

# 11. verify_bundle extensions and failure codes

Human-side checks become verifier-enforced by extending `verify_bundle`:

## 11.1 New failure codes (verifier-visible)

Add to the existing failure codes list:

### Empathy
- `EMPATHY_MISSING_EVIDENCE`
- `EMPATHY_MISSING_FIELDS`
- `EMPATHY_LOW_SCORE`

### Purpose
- `PURPOSE_MISSING_EVIDENCE`
- `PURPOSE_MISSING_FIELDS`
- `PURPOSE_LOW_SCORE`

### Humility
- `HUMILITY_MISSING_EVIDENCE`
- `HUMILITY_INSUFFICIENT_DISCLOSURE`
- `HUMILITY_UNCERTAINTY_UNDERSTATED`
- `HUMILITY_LOW_SCORE`

### Perspective
- `PERSPECTIVE_MISSING_EVIDENCE`
- `PERSPECTIVE_INSUFFICIENT_ROLES`
- `PERSPECTIVE_LOW_SCORE`
- `PERSPECTIVE_COUNCIL_REQUIRED`

### Truth
- `TRUTH_CLAIMSET_MISSING`
- `TRUTH_SOURCE_MISSING`
- `TRUTH_SOURCE_HASH_MISMATCH`
- `TRUTH_QUOTE_NOT_FOUND`
- `TRUTH_PATH_NOT_FOUND`
- `TRUTH_NUMERIC_NOT_FOUND`
- `TRUTH_UNCALIBRATED_CONFIDENCE`
- `TRUTH_COVERAGE_TOO_LOW`
- `TRUTH_LOW_SCORE`

### Fitness
- `FITNESS_MISSING_EVIDENCE`
- `FITNESS_CRITERIA_EMPTY`
- `FITNESS_INCOMPLETE`
- `FITNESS_SUBJECTIVE_REQUIRES_HUMAN`
- `FITNESS_LOW_SCORE`

## 11.2 Verifier algorithm extension

When receipt includes `human.version == "HUMAN-0.1"` OR policy declares human checks required:

1) Load each referenced evidence file
2) Recompute score deterministically using the algorithms in Sections 2–7
3) Compare to `HumanCheckResult.score` in receipt
   - mismatch → fail `POLICY_VIOLATION` (or a dedicated `HUMAN_SCORE_MISMATCH`)
4) Enforce threshold rules based on lock level / policy
5) Enforce HITL rules for HUMILITY and FITNESS (presence of approval artifact)

---

# 12. Testing and benchmarking (human-side golden fixtures)

This section adds to the existing `workc_testkit` approach.

## 12.1 Fixture layout (recommended)

```
workc_scenarios/fixtures/human_golden/v0.1/
  empathy_pass/
    empathy_report.json
    expected.json
  empathy_fail_shallow/
    empathy_report.json
    expected.json
  truth_fail_missing_source/
    claimset.json
    expected.json
  perspective_require_council/
    perspective_report.json
    expected.json
  humility_requires_hitl/
    humility_report.json
    expected.json
  fitness_subjective_requires_human/
    fitness_report.json
    expected.json
```

Each `expected.json` contains:

```json
{
  "check_id": "EMPATHY-0.1",
  "expected_score": 820,
  "expected_passed": true,
  "expected_flags": [],
  "expected_failure_codes": []
}
```

## 12.2 Unit tests (required)

For each module (Empathy/Purpose/Humility/Perspective/Truth/Fitness):

- Parse fixture JSON
- Compute score
- Assert exact `expected_score` and pass/fail
- Assert expected flags

## 12.3 Property-based tests (recommended)

- **Monotonicity (Truth)**: adding a valid source to a claim MUST NOT decrease `truth` score.
- **Monotonicity (Perspective)**: adding a missing required role MUST NOT decrease coverage score.
- **Calibration penalty (Humility)**: decreasing declared uncertainty below `u_min` MUST NOT increase score.
- **Determinism**: identical inputs → identical scores.

## 12.4 Scenario tests (integration)

Add scenarios that run a full loop and include human evidence files, then verify:

- `verify_bundle` PASS when thresholds met
- `verify_bundle` FAIL with specific human failure codes when not met

---

# 13. Default thresholds and calibration guidance

Default thresholds in Sections 2–7 are starting points.

## 13.1 Empirical calibration loop (offline)

Use receipts to tune thresholds:

- Let `Y=1` if loop reaches LOCK without human override and passes acceptance tests; else 0.
- Let `X` be the human check scores.

Fit monotone calibration maps (e.g., isotonic regression) for each check score → `P(Y=1)`.

Choose thresholds so:

\[
P(Y=1 \mid score \ge threshold) \ge 1 - \epsilon
\]

with default `\epsilon=0.1`.

## 13.2 Keep thresholds monotone with lock level

Policies MUST maintain monotonicity:

- Increasing lock level MUST NOT lower required thresholds.
- Increasing risk MUST NOT lower required thresholds.
- Introducing subjective fitness MUST NOT lower HITL requirements.

---

# Appendix A. JSON schema sketches (human evidence files)

(Implementations SHOULD generate JSON Schemas via `schemars` in Rust.)

- `EmpathyReport`
- `PurposeReport`
- `HumilityReport`
- `PerspectiveReport`
- `ClaimSet`
- `FitnessReport`
- `HumanApproval`

---

# Appendix B. Example fixtures (inputs + expected results)

## B1. EMPATHY pass (illustrative)

`empathy_report.json`
```json
{
  "version": "EMPATHY-0.1",
  "recipient": "Motus engineers implementing HUMAN checks in Rust with deterministic algorithms and verify_bundle integration.",
  "prior_knowledge": "They know Rust, hashing, and Motus bundles, but want precise definitions and formulas.",
  "needs": "They need integer-only permille scoring formulas, deterministic algorithms, and integration steps for verify_bundle.",
  "confusion_risks": "Ambiguity in definitions, anchors, or evidence formats will make deterministic verification hard.",
  "trust_builders": "Provide evidence paths, receipts, and verify steps with sources, tests, and citations."
}
```

Expected: score ≥ 750, passed for Committed.

## B2. TRUTH fail (missing sources)

`claimset.json`
```json
{
  "version": "TRUTH-0.1",
  "coverage_declared": 900,
  "claims": [
    {
      "claim_id": "C1",
      "claim_type": "Fact",
      "statement": "Motus uses SHA-256 for proof digests.",
      "confidence": 900,
      "sources": []
    }
  ]
}
```

## B3. PURPOSE pass (illustrative)

`purpose_report.json`
```json
{
  "version": "PURPOSE-0.1",
  "why_it_matters": "This prevents building an agent system that feels correct but is untrustworthy to users.",
  "problem_solved": "It defines deterministic, verifiable human-side checks (empathy, truth, perspective, etc.).",
  "beneficiaries": "Motus users and engineers who need predictable quality gates.",
  "cost_of_wrong": "If we get this wrong, users will rubber-stamp approvals or ship incorrect outputs with false confidence.",
  "success_criteria": ["All checks score deterministically", "verify_bundle can recompute scores", "HITL triggers are predictable"],
  "devils_advocate": "Even with checklists, content can still be low-quality; we must not confuse structure with true understanding."
}
```

## B4. HUMILITY triggers HITL

`humility_report.json`
```json
{
  "version": "HUMILITY-0.1",
  "assumptions": [
    "The consumer of these specs prefers deterministic checklists to vague guidance.",
    "Some qualities (tone/brand/legal) still require HITL until we have a signing model.",
    "Lens quality aggregate is available by DECIDE and is trustworthy enough for calibration."
  ],
  "uncertainties": [
    "Exact permille thresholds may need empirical tuning on real workloads.",
    "Some domains require richer provenance models than REL-0.1.",
    "Claim coverage heuristics can undercount structured outputs."
  ],
  "uncertainty_permille": 800,
  "human_double_checks": [
    "Review subjective FITNESS criteria (tone, brand, legal) before publishing.",
    "Spot-check TRUTH claims that are high-impact but sourced from low-reliability inputs."
  ]
}
```

Expected: `requires_human=true` before LOCK for lock level ≥ Committed.

## B5. PERSPECTIVE insufficient roles (Published)

`perspective_report.json`
```json
{
  "version": "PERSPECTIVE-0.1",
  "perspectives": [
    {
      "role": "Skeptic",
      "points": ["These checks could be gamed by verbose but empty text."],
      "severity": ["Strong"]
    },
    {
      "role": "Novice",
      "points": ["I need clear defaults so I don't configure everything manually."],
      "severity": ["Noted"]
    }
  ],
  "synthesis": null,
  "council_artifacts": null
}
```

Expected: fail `PERSPECTIVE_INSUFFICIENT_ROLES` at lock level Published and suggest/require `STRAT-009 Agent Council`.

## B6. FITNESS subjective requires human

`fitness_report.json`
```json
{
  "version": "FITNESS-0.1",
  "criteria": [
    {
      "criterion_id": "F1",
      "description": "Spec compiles as Rust types and algorithms (deterministic)",
      "kind": "Deterministic",
      "evidence": "evidence/tests/rust_compile.log"
    },
    {
      "criterion_id": "F2",
      "description": "Tone is appropriate and not misleading (subjective)",
      "kind": "HumanJudgment",
      "evidence": null
    }
  ],
  "context_notes": "This is for engineers implementing Motus; clarity and determinism matter more than marketing tone.",
  "subjective_flags": ["tone"]
}
```

Expected: flag `FIT_SUBJECTIVE` and require human approval artifact before LOCK.

---

**End of MOTUS-HUMAN-SPEC-V0.1**

