# MOTUS-SPEC-V0.1

**Spec Version:** 0.1.0  
**Date:** 2025-12-24  
**Status:** Implementation Contract (normative “MUST/SHOULD/MAY” language)

This document formalizes Motus “agent empowerment” into deterministic algorithms and data formats that can be implemented end-to-end (primarily in Rust) and verified by an independent verifier.

Motus is an execution kernel that makes agent work:
- **Auditable** (append-only event logs, receipts),
- **Governable** (policy gates, effects, HITL),
- **Deterministic** (canonicalization, stable hashing),
- **Composable** (nested work graphs / child loops),
- **Benchmarked** (reproducible scenario fixtures + microbenches).

The design matches the Motus primer and Work Compiler spec: a Work Compiler runs an OODA loop (Observe→Orient→Decide→Act→Verify→Lock) and emits receipts and proof digests for verification and replay.

---

## Table of contents

0. Glossary and notation  
1. Consolidated type definitions (Rust)  
2. Algorithms (pseudocode + Rust signatures)  
3. Merkle root formulas and domain separators  
4. Canonicalization spec CJ-0.1 (byte-level)  
5. FSM transition rules FSM-0.1  
6. `verify_bundle` specification and failure codes  
7. Property-based test specifications  
8. Golden bundle specifications (test vectors)  
9. Benchmark specifications  
10. Version compatibility matrix  
11. Answers to Q11–Q15 (mathematically rigorous)  
12. JSON schemas (`test_report.json`, `bench_report.json`)  

---

# 0. Glossary and notation

### Core entities

- **Loop**: One Work Compiler execution of an OODA cycle with an eventual **Lock** event. Identified by `LoopId`.
- **Work Graph**: A DAG (tree in v0.1) of loops (parent spawns children). Each loop has a receipt. Parents commit to child receipts via `workgraph_root`.
- **Receipt**: Canonical JSON summary of the loop outcome with an `integrity` block containing hashes/roots and a `proof_digest`.
- **Bundle**: On-disk directory containing:
  - `receipt.json`
  - `events.jsonl`
  - `manifest.json`
  - `evidence/**` files (optional but typical)

### Hashing notation

- `H(x)` = SHA-256 of bytes `x` (32 bytes).
- `||` = byte concatenation.
- All hex strings are lowercase, no `0x`, exactly 64 hex chars for `Hash256`.

### Versions (v0.1.0)

- Canonical JSON: `CJ-0.1`
- Proof digest: `PROOF-0.1`
- FSM: `FSM-0.1`
- Effect normalization/compression: `ENF-0.1`
- Bundle format: `BUNDLE-0.1`

### Domain separators (ASCII bytes)

All domain separators are **ASCII** and included **verbatim** in hash inputs:

- `DS_RECEIPT = "MOTUS|RECEIPT|0.1|"`
- `DS_EVT     = "MOTUS|EVT|0.1|"`
- `DS_PROOF   = "MOTUS|PROOF|0.1|"`

Merkle root domain separators are parameterized by root type `T`:
- `DS_LEAF(T)  = "MOTUS|MRKL|{T}|LEAF|0.1|"`
- `DS_NODE(T)  = "MOTUS|MRKL|{T}|NODE|0.1|"`
- `DS_EMPTY(T) = "MOTUS|MRKL|{T}|EMPTY|0.1|"`

Where `T ∈ {EVENTLOG, ARTIFACTS, EVIDENCE, LENS, EFFECTS, GATES, VERIFICATION, WORKGRAPH}`.

---

# 1. Consolidated type definitions (Rust)

This section is the **single source of truth** for core data structures and their serialization expectations.

> **Serialization rule:** All JSON emitted by Motus MUST be CJ-0.1 canonical JSON bytes (Section 4).  
> Receipts, manifests, and per-line event JSON MUST be canonicalized before hashing and before writing to disk.

## 1.1 Primitive newtypes

```rust
use serde::{Serialize, Deserialize};

/// 0..=1000 inclusive. 1000 == 100%.
#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord, Hash, Serialize, Deserialize)]
pub struct Permille(pub u16);

/// Milliseconds.
#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord, Hash, Serialize, Deserialize)]
pub struct Millis(pub u64);

/// 32-byte hash, serialized as lowercase hex in JSON.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub struct Hash256(pub [u8; 32]);

/// Loop identifier. Serialized as UUID string in JSON.
#[derive(Clone, Debug, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub struct LoopId(pub uuid::Uuid);

/// Event identifier. Serialized as UUID string in JSON.
#[derive(Clone, Debug, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub struct EventId(pub uuid::Uuid);
```

### Required invariants

- `Permille.0 <= 1000` MUST hold.
- `Hash256` MUST be exactly 32 bytes.
- All UUID strings MUST be lowercase and hyphenated (standard `uuid` formatting).

## 1.2 FSM and runtime enums

```rust
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum Phase {
    Observe,
    Orient,
    Decide,
    Act,
    Verify,
    Lock,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum LockLevel {
    Draft,
    Staged,
    Committed,
    Published,
    Immutable,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub enum SpawnMode {
    Sequential,
    Parallel,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub enum Transition {
    /// Move to the next phase (typical).
    Next { to: Phase },

    /// Repeat a phase (e.g., retry).
    Repeat { phase: Phase, reason: String },

    /// Backtrack to an earlier phase (e.g., Verify→Orient).
    Backtrack { to: Phase, reason: String },

    /// Spawn child loops (sub-work). Parent continues depending on policy.
    Spawn {
        mode: SpawnMode,
        children: Vec<ChildSpec>,
        reason: String,
    },

    /// Halt execution (fatal).
    Halt { reason: String },

    /// Finish loop; lock will follow.
    Complete { outcome: Outcome },
}
```



## 1.2.1 LoopState, budgets, and phase results

`LoopState` is the in-memory state machine backing the Work Compiler. It is **not** directly serialized
into receipts, but receipts are projections of (parts of) this state.

```rust
#[derive(Clone, Debug)]
pub struct LoopBudgets {
    /// Maximum number of Verify→Orient backtracks allowed.
    pub max_backtracks: u32,
    /// Maximum number of Act repeats (retries) allowed.
    pub max_act_retries: u32,
    /// Maximum number of total events allowed (DoS protection).
    pub max_events: u32,
}

#[derive(Clone, Debug)]
pub struct LoopState {
    pub loop_id: LoopId,
    pub parent_loop_id: Option<LoopId>,

    pub intent: Intent,
    pub actor: Actor,
    pub lock_level: LockLevel,

    pub phase: Phase,
    pub phase_trace: Vec<Phase>,

    pub lens: Option<LensSnapshot>,

    /// Declared effects (policy-governed intent).
    pub effects_declared: Vec<Effect>,
    /// Observed effects (measured execution).
    pub effects_observed: Vec<Effect>,

    pub artifacts: Artifacts,
    pub decisions: Vec<DecisionRecord>,
    pub strategies: StrategyState,
    pub verification: VerificationBlock,
    pub gates: Vec<GateResult>,
    pub children: Vec<ChildEdge>,
    pub errors: Vec<ErrorRecord>,
    pub hitl: Vec<HitlRecord>,

    pub budgets: LoopBudgets,
}

#[derive(Clone, Debug)]
pub enum PhaseResult {
    Ok,
    NeedsBacktrack { to: Phase, reason: String },
    NeedsRepeat { phase: Phase, reason: String },
    SpawnChildren { mode: SpawnMode, children: Vec<ChildSpec>, reason: String },
    Halt { reason: String },
}
```

**Invariants**
- `phase_trace` MUST append the phase value once per event emitted for that phase.
- Budget counters MUST be decremented deterministically based on transitions.

## 1.3 Intent, outcome, actor

```rust
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct Intent {
    pub description: String,
    pub source: IntentSource,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub enum IntentSource {
    Human,
    ParentLoop,
    Trigger,
    Policy,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct Outcome {
    pub status: OutcomeStatus,
    pub description: String,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub enum OutcomeStatus {
    success,
    partial,
    failed,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct Actor {
    pub r#type: ActorType,
    pub name: String,
    /// Optional: model identifier (e.g., "gpt-5.2-pro").
    pub model: Option<String>,
    /// Optional: model digest (e.g., SHA-256 of model card/config).
    pub model_digest: Option<Hash256>,
    /// Optional: email for human actors.
    pub email: Option<String>,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub enum ActorType {
    human,
    agent,
    automation,
}
```

## 1.4 Artifacts

Artifacts are references to inputs/outputs (files, URIs) with content hashes.

```rust
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct ArtifactRef {
    pub path: String,        // canonical path (Section 2.10 path canon)
    pub sha256: Hash256,     // SHA-256 of content bytes (external to bundle)
    pub size_bytes: Option<u64>,
    pub kind: Option<ArtifactKind>,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub enum ArtifactKind {
    File,
    Directory,
    Uri,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct Artifacts {
    pub inputs: Vec<ArtifactRef>,   // MUST be sorted (path, sha256) in CJ
    pub outputs: Vec<ArtifactRef>,  // MUST be sorted (path, sha256) in CJ
}
```

## 1.5 Errors

```rust
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub enum ErrorClass {
    Recoverable,
    Unrecoverable,
    PatternFailure,
    Catastrophic,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct ErrorRecord {
    pub phase: Phase,
    pub class: ErrorClass,
    pub code: String,
    pub message: String,
    pub retryable: bool,
    pub evidence: Option<String>, // path under evidence/
}
```

## 1.6 Event log

Events are append-only envelopes written line-by-line to `events.jsonl`. Each line MUST be CJ-0.1 canonical JSON.

```rust
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct EventEnvelope {
    pub event_id: EventId,
    pub loop_id: LoopId,
    pub seq: u32,
    pub ts_utc: String,     // RFC3339 UTC (e.g., "2025-12-24T00:00:00Z")
    pub phase: Phase,
    pub kind: String,       // stable string, e.g. "IntentSet"
    pub payload: PhaseEventPayload,

    pub prev_event_hash: Hash256,
    pub event_hash: Hash256,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(tag = "type", content = "data")]
pub enum PhaseEventPayload {
    /// Intent + actor identity.
    IntentSet { intent: Intent, actor: Actor },

    /// Observe phase signals summary.
    SignalsCaptured { evidence: String, signals_count: u32 },

    /// Orient phase lens assembly summary.
    LensAssembled { lens_id: String, items_count: u32, quality: LensQuality },

    /// Decide phase plan selection.
    PlanChosen { plan: String, effects_declared: Vec<Effect> },

    /// Act phase execution.
    SkillExecuted {
        skill: String,
        evidence: String,
        artifacts_out: Vec<ArtifactRef>,
        effects_observed: Vec<Effect>,
    },

    /// Act phase error.
    ActError { error: ErrorRecord },

    /// Verify phase results.
    VerificationRun { passed: bool, results: Vec<CheckResult> },

    /// HITL prompt/decision.
    HitlPrompt { record: HitlRecord },
    HitlDecision { record: HitlRecord },

    /// Child loop spawn/join.
    ChildSpawned { spawn_index: u32, child_loop_id: LoopId, critical: bool },
    ChildJoined  { child_loop_id: LoopId, child_proof_digest: Hash256 },

    /// Lock.
    Locked { lock_level: LockLevel, outcome: Outcome },
}
```

> **Note:** The `kind` string MUST be redundant with `payload` variant name for human readability, but verifiers SHOULD rely on the typed `payload` when available.

## 1.7 Lens types

```rust
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct LensSnapshot {
    pub lens_id: String,
    pub created_utc: String,
    pub items: Vec<LensItem>,      // MUST be sorted (kind, uri, sha256) in CJ
    pub quality: LensQuality,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct LensItem {
    pub kind: String,       // "file" | "dir" | "uri" | "receipt" | ...
    pub uri: String,        // canonical identifier (path or URL)
    pub sha256: Hash256,    // content hash (or receipt hash)
    pub ts_utc: String,     // source timestamp (for freshness)
    pub provenance: String, // "fs" | "network" | "receipt" | "user" | ...
    pub weight: Option<Permille>, // optional importance weight for scoring
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct LensQuality {
    pub coverage: Permille,
    pub freshness: Permille,
    pub conflict: Permille,
    pub provenance: Permille,
    pub aggregate: Permille, // defined by Algorithm 13
}
```

## 1.8 Effects

```rust
#[derive(Clone, Debug, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum EffectOp {
    ReadFS,
    WriteFS,
    Network,
    Exec,
    Publish,
}

#[derive(Clone, Debug, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub struct Effect {
    pub op: EffectOp,
    pub selector: String, // canonical selector string (Section 2.10)
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct EffectSet {
    pub enf_version: String, // "ENF-0.1"
    pub k: u32,              // compression cap
    pub executed_raw: Vec<Effect>,
    pub declared: Vec<Effect>, // normalized and compressed
    pub compression: Option<serde_json::Value>,
}
```

## 1.9 Verification and gates

```rust
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub enum VerificationLevel {
    Syntactic,
    Semantic,
    Regression,
    Acceptance,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct VerificationSpec {
    pub level: VerificationLevel,
    pub checks_required: Vec<String>,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct CheckResult {
    pub level: VerificationLevel,
    pub check_id: String,  // MUST be unique within receipt (include attempt if needed)
    pub passed: bool,
    pub evidence: Option<String>,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct GateResult {
    pub phase: Phase,
    pub gate_id: String,
    pub passed: bool,
    pub evidence: Option<String>,
}
```

## 1.10 Strategy types

```rust
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct Strategy {
    pub strategy_id: String,     // e.g., "STRAT-009"
    pub version: String,         // e.g., "0.1"
    pub name: String,
    pub triggers: Vec<StrategyTrigger>, // OR-of-triggers in v0.1
    pub steps: Vec<String>,      // high-level pattern steps (human readable)
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct StrategyTrigger {
    pub signal: String,
    pub confidence_threshold: Permille,
    pub weight: Option<Permille>,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct StrategySuggestion {
    pub strategy_id: String,
    pub match_permille: Permille,
    pub trigger: String,
    pub explanation: Vec<String>, // deterministic explanation strings
}
```

## 1.11 Child loops and work graph

```rust
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct ChildSpec {
    pub intent: Intent,
    pub critical: bool,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct ChildEdge {
    pub spawn_index: u32,              // spawn order, 0..n-1
    pub child_loop_id: LoopId,
    pub critical: bool,
    pub child_proof_digest: Hash256,
    pub outcome_status: OutcomeStatus, // child's final outcome
}
```

## 1.12 HITL records

```rust
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct HitlRecord {
    pub kind: HitlKind,
    pub ts_utc: String,

    // Prompt fields
    pub required: Option<bool>,
    pub reason: Option<String>,
    pub p_override_permille: Option<Permille>,
    pub loss_ms: Option<Millis>,
    pub cost_ms: Option<Millis>,
    pub evi_ms: Option<Millis>,

    // Decision fields
    pub approved: Option<bool>,
    pub approver: Option<Actor>,
    pub note: Option<String>,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub enum HitlKind {
    Prompt,
    Decision,
}
```

## 1.13 Work receipt and integrity

```rust
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct WorkReceipt {
    pub receipt_version: String,   // "0.1.0"

    pub loop_id: LoopId,
    pub parent_loop_id: Option<LoopId>,
    pub timestamp_utc: String,     // lock timestamp

    pub intent: Intent,
    pub outcome: Outcome,
    pub actor: Actor,

    pub lock_level: LockLevel,

    /// The realized phase trace (including repeats/backtracks).
    pub phase_sequence: Vec<Phase>,

    pub artifacts: Artifacts,
    pub lens: LensSnapshot,
    pub effects: EffectSet,

    pub decisions: Vec<DecisionRecord>,
    pub strategies: StrategyState,
    pub verification: VerificationBlock,
    pub gates: Vec<GateResult>,
    pub children: Vec<ChildEdge>,
    pub errors: Vec<ErrorRecord>,
    pub hitl: Vec<HitlRecord>,

    pub integrity: IntegrityBlock,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct DecisionRecord {
    pub point: String,
    pub choice: String,
    pub rationale: String,
    pub alternatives_rejected: Vec<String>,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct StrategyState {
    pub suggestions: Vec<StrategySuggestion>,
    pub used: Option<serde_json::Value>, // v0.1 allows opaque payload for applied strategy
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct VerificationBlock {
    pub spec: VerificationSpec,
    pub results: Vec<CheckResult>,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct IntegrityBlock {
    pub cj_version: String,     // "CJ-0.1"
    pub proof_version: String,  // "PROOF-0.1"
    pub fsm_version: String,    // "FSM-0.1"
    pub enf_version: String,    // "ENF-0.1"

    pub policy_id: String,
    pub policy_hash: Hash256,

    pub receipt_hash: Hash256,
    pub proof_digest: Hash256,

    pub roots: BundleRoots,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct BundleRoots {
    pub event_log_root: Hash256,
    pub artifacts_root: Hash256,
    pub evidence_root: Hash256,
    pub lens_root: Hash256,
    pub effects_root: Hash256,
    pub gates_root: Hash256,
    pub verification_root: Hash256,
    pub workgraph_root: Hash256,
}
```

## 1.14 Bundle manifest

```rust
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct BundleManifest {
    pub bundle_version: String, // "BUNDLE-0.1"
    pub loop_id: LoopId,
    pub created_utc: String,
    pub files: Vec<FileHashEntry>, // MUST be sorted by path in CJ
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct FileHashEntry {
    pub path: String,    // relative path inside bundle directory
    pub sha256: Hash256, // SHA-256 of file bytes on disk
    pub size_bytes: u64,
}
```



## 1.14.1 Bundle on-disk layout (BUNDLE-0.1)

A **bundle** is a directory with the following required files:

```text
bundle/
  receipt.json
  events.jsonl
  manifest.json
  evidence/            (optional; if present must be listed in manifest)
    ...
```

### Required rules

- `receipt.json` MUST be CJ-0.1 canonical JSON bytes of a `WorkReceipt`.
- `events.jsonl` MUST be UTF-8 with **one CJ-0.1 canonical JSON object per line**.
  - The file SHOULD end with a trailing `\n`.
- `manifest.json` MUST be CJ-0.1 canonical JSON bytes of a `BundleManifest`.
- `manifest.files` MUST include hashes for **all files except `manifest.json` itself**:
  - at minimum `receipt.json` and `events.jsonl`
  - and every `evidence/**` file that exists or is referenced.

### Minimal example (illustrative)

`manifest.json`:
```json
{"bundle_version":"BUNDLE-0.1","created_utc":"2025-12-24T00:00:00Z","files":[{"path":"events.jsonl","sha256":"...","size_bytes":123},{"path":"receipt.json","sha256":"...","size_bytes":456}],"loop_id":"11111111-1111-1111-1111-111111111111"}
```

`events.jsonl`:
```json
{"event_hash":"...","event_id":"...","kind":"IntentSet","loop_id":"...","payload":{"actor":{"model":"gpt-5.2-pro","name":"motus-agent","type":"agent"},"intent":{"description":"...","source":"human"}},"phase":"Observe","prev_event_hash":"000000...","seq":0,"ts_utc":"2025-12-24T00:00:00Z"}
```

## 1.15 Policy trait

Policy is the governance layer. It is pure/deterministic over receipts and context.

```rust
pub trait Policy: Send + Sync {
    fn policy_id(&self) -> &'static str;
    fn policy_hash(&self) -> Hash256;

    /// Default effect compression cap K for ENF-0.1.
    fn default_effect_cap_k(&self) -> u32 { 50 }

    /// Lens quality thresholds (permille).
    fn min_lens_quality_for_decide(&self) -> Permille;
    fn min_lens_quality_for_lock(&self, lock_level: LockLevel) -> Permille;

    /// Verification requirements given lock level and risk.
    fn required_verification(&self, lock_level: LockLevel, risk: RiskScore) -> VerificationSpec;

    /// Compute HITL expected value of intervention; decides if human checkpoint required.
    fn hitl_requirement(&self, receipt: &WorkReceipt, risk: RiskScore) -> HitlRequirement;

    /// Policy compliance check for verify_bundle.
    fn verify_policy_compliance(&self, receipt: &WorkReceipt) -> Result<(), PolicyViolation>;
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct RiskScore(pub u32); // policy-defined scale

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct HitlRequirement {
    pub required: bool,
    pub reason: String,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct PolicyViolation {
    pub code: String,
    pub message: String,
}
```


## 1.16 Minimal required API surface (Work Compiler + runtime adapters)

This section specifies the minimum trait surface required to implement Motus v0.1 while keeping
the Work Compiler deterministic. Implementations MAY add methods, but MUST preserve these semantics.

### Work compiler API

```rust
pub trait WorkCompiler {
    /// Run a loop and return a receipt. The implementation MUST also persist a bundle
    /// (receipt/events/manifest/evidence) for later verification.
    fn run_loop(&self, intent: Intent, lock_level: LockLevel) -> Result<WorkReceipt, RunError>;

    /// Convenience: verify a persisted bundle.
    fn verify_bundle(&self, bundle_path: &std::path::Path) -> VerifyResult;
}
```

### Runtime adapters API

The Work Compiler itself is deterministic, but calls into adapters to interact with the outside world.
All adapter results MUST be recorded in events/evidence so that the resulting bundle is verifiable.

```rust
pub trait RuntimeAdapters {
    /// Observe: return signals and (optionally) an evidence path under evidence/.
    fn observe_signals(&self, state: &LoopState) -> Result<ObserveOut, AdapterError>;

    /// Orient: assemble a lens snapshot.
    fn assemble_lens(&self, state: &LoopState) -> Result<LensSnapshot, AdapterError>;

    /// Act: execute skills under declared effects and return observed effects + artifacts.
    fn execute_act(&self, state: &LoopState) -> Result<ActOut, AdapterError>;

    /// Verify: run checks and return results.
    fn run_verification(&self, state: &LoopState, spec: &VerificationSpec) -> Result<Vec<CheckResult>, AdapterError>;

    /// HITL: if required, request approval and return a Decision record.
    fn request_hitl_decision(&self, prompt: &HitlRecord) -> Result<HitlRecord, AdapterError>;

    /// Spawn a child loop. The parent MUST later obtain the child proof digest.
    fn spawn_child(&self, child: &ChildSpec) -> Result<LoopId, AdapterError>;

    /// Fetch a child receipt/bundle proof digest from storage.
    fn fetch_child_proof(&self, child_loop_id: &LoopId) -> Result<Hash256, AdapterError>;

    /// Persist a bundle to durable storage and return the bundle path (or URI).
    fn persist_bundle(&self, receipt: &WorkReceipt, events: &[EventEnvelope]) -> Result<std::path::PathBuf, AdapterError>;
}

pub struct ObserveOut {
    pub signals_count: u32,
    pub evidence: Option<String>,
}

pub struct ActOut {
    pub evidence: Option<String>,
    pub artifacts_out: Vec<ArtifactRef>,
    pub effects_observed: Vec<Effect>,
}
```

**Determinism requirement:** given equal adapter outputs, the compiler MUST produce identical bundles
(including `proof_digest`).


---

# 2. Algorithms (pseudocode + Rust signatures)

This section defines the required algorithms. All algorithms MUST be deterministic given their inputs.

## Algorithm 1 — CJ-0.1 canonicalization

**Purpose:** Convert JSON-like values into a unique UTF-8 byte sequence.

**Rust signature**
```rust
pub fn cj01_canonical_bytes(value: &serde_json::Value) -> Vec<u8>;
```

**Rules:** See Section 4.

---

## Algorithm 2 — Event hash chain (EVT-0.1)

Each event line includes `prev_event_hash` and `event_hash`.

**Hash input:**
- Let `Eᵢ` be the event object **excluding** `event_hash` (but including `prev_event_hash`).
- `event_hashᵢ = H( DS_EVT || CJ(Eᵢ) )`

For the first event (`seq=0`), `prev_event_hash = 32*0x00`.

**Rust signature**
```rust
pub fn compute_event_hash(ev_without_event_hash: &EventEnvelope) -> Hash256;
pub fn verify_event_chain(events: &[EventEnvelope]) -> Result<(), VerifyError>;
```

**Pseudocode**
```text
prev = 0x00..00 (32 bytes)
for i in 0..n-1:
  assert events[i].seq == i
  assert events[i].prev_event_hash == prev
  h = SHA256( DS_EVT || CJ(events[i] without event_hash) )
  assert events[i].event_hash == h
  prev = h
```

---

## Algorithm 3 — Merkle root (MRKL-0.1)

Given leaf byte strings `L0..L(n-1)`:

- If `n=0`: `root = H( DS_EMPTY(T) )`
- Else:
  - `leaf_hashᵢ = H( DS_LEAF(T) || Lᵢ )`
  - While more than 1 hash remains:
    - If odd length, duplicate last hash.
    - Pairwise combine:
      - `node_hash = H( DS_NODE(T) || left || right )`

**Rust signature**
```rust
pub fn merkle_root<T: MerkleTag>(leaves: &[Vec<u8>]) -> Hash256;
```

---

## Algorithm 4 — Proof digest (PROOF-0.1)

**Definition:** A deterministic “mathematical checksum” for a loop bundle.  
If `verify_bundle` passes, recomputing `proof_digest` MUST equal `receipt.integrity.proof_digest`.

### Inputs (fixed order, all 32 bytes)

1. `receipt_hash`
2. `event_log_root`
3. `artifacts_root`
4. `evidence_root`
5. `lens_root`
6. `effects_root`
7. `gates_root`
8. `verification_root`
9. `workgraph_root`

### Formula
`proof_digest = H( DS_PROOF || receipt_hash || event_log_root || artifacts_root || evidence_root || lens_root || effects_root || gates_root || verification_root || workgraph_root )`

**Rust signature**
```rust
pub fn compute_proof_digest(receipt_hash: Hash256, roots: &BundleRoots) -> Hash256;
```

---

## Algorithm 5 — Receipt projection (events → receipt)

**Purpose:** The runtime may build the receipt purely from events to avoid inconsistent summaries.

**Rust signature**
```rust
pub fn project_receipt(events: &[EventEnvelope]) -> Result<WorkReceiptWithoutIntegrity, ProjectionError>;
```

**Core rule:** The projected receipt MUST be a deterministic fold over events:
- Intent/actor from `IntentSet`
- Lens from `LensAssembled`
- Declared effects from `PlanChosen`
- Observed effects and artifacts from `SkillExecuted`
- Verification from `VerificationRun`
- HITL from `HitlPrompt` + `HitlDecision`
- Children from `ChildSpawned` + `ChildJoined`
- Outcome/lock_level from `Locked`
- Phase trace from `events[i].phase`

> **v0.1 requirement:** Implementations MAY still directly populate receipts without projection, but projection MUST exist and MUST produce a canonical equivalent receipt for regression fixtures.

---

## Algorithm 6 — FSM runner (FSM-0.1)

**Rust signature**
```rust
pub fn run_fsm(
  intent: Intent,
  policy: &dyn Policy,
  adapters: &dyn RuntimeAdapters,
) -> Result<WorkReceipt, RunError>;
```

**High-level pseudocode**
```text
state = LoopState::new(intent)
phase = Observe
trace = []

while true:
  trace.push(phase)

  result = run_phase(phase, state)
  transition = next_transition(state, phase, result)

  apply_transition(state, transition)

  if transition is Halt: return failure receipt
  if phase == Lock and locked: return receipt
  phase = transition.target_phase
```

Phase bodies call runtime adapters:
- Observe: capture signals
- Orient: assemble lens + compute quality
- Decide: choose plan + declare effects
- Act: execute skills, record observed effects/artifacts/errors
- Verify: run verifiers, record check results
- Lock: compute HITL requirement, request approval if needed, then lock/publish

---

## Algorithm 7 — NEXT transition function

**Rust signature**
```rust
pub fn next_transition(
  state: &LoopState,
  phase: Phase,
  phase_result: &PhaseResult,
  policy: &dyn Policy
) -> Transition;
```

**Deterministic decision rules (priority-ordered):**
1. If `phase_result` is catastrophic → `Halt`.
2. If `phase == Verify` and verification failed:
   - If retry budget available → `Backtrack { to: Orient }` (default) OR `Repeat { phase: Act }` based on error class.
3. If lens quality below threshold:
   - If `phase ∈ {Decide, Act}` → `Backtrack { to: Orient }`.
   - Else `Repeat { phase: Observe }`.
4. If child work required (policy or strategy) → `Spawn`.
5. Else advance phase (`Next`) until `Lock`, then `Complete`.

---

## Algorithm 8 — `verify_bundle` (BUNDLE-0.1)

See Section 6 for full step-by-step.

**Rust signature**
```rust
pub fn verify_bundle(bundle_path: &std::path::Path, policy: &dyn Policy) -> VerifyResult;
```

---

## Algorithm 9 — FSM replay validator

**Purpose:** Validate that `events.jsonl` is consistent with FSM-0.1.

**Rust signature**
```rust
pub fn validate_fsm_trace(events: &[EventEnvelope]) -> Result<(), FsmError>;
```

Rules: Section 5.

---

## Algorithm 10 — ENF-0.1 effect normalization

**Purpose:** deterministic normalization of effect lists.

**Rust signature**
```rust
pub fn normalize_effects(effects: &[Effect]) -> Vec<Effect>;
```

**Normalization steps**
1. Canonicalize selectors (Algorithm 10.1 below).
2. Deduplicate identical `(op, selector)`.
3. Sort by `(op, selector)` lexicographically.
4. Return list.

### Algorithm 10.1 — Selector canonicalization (paths + URIs)

Selectors are opaque strings but MUST follow these canonical forms:

- FS: `fs:{path}` where `path` uses `/`, no `..`, no trailing `/.`, no duplicate slashes.
- Network: `net:{scheme}://{host}/{path...}` with lowercase host, normalized path.
- Exec: `exec:{program}` (coarse in v0.1).
- Publish: `pub:{target}` (policy-defined).

---

## Algorithm 11 — Effect compression (TrieMerge-v0.1)

See Q11 (Section 11) for the rigorous algorithm and worked example.

**Rust signature**
```rust
pub fn compress_effects_trie_merge(effects: &[Effect], k: u32) -> Vec<Effect>;
```

---

## Algorithm 12 — Lens quality scoring

This produces the four components (coverage, freshness, conflict, provenance).

**Rust signature**
```rust
pub fn score_lens_quality(snapshot: &LensSnapshot, now_utc: &str) -> LensQuality;
```

- Freshness is defined rigorously in Q12.
- Coverage/conflict/provenance are policy-parameterized but MUST be deterministic.

---

## Algorithm 13 — Lens aggregate quality

**Definition:** `aggregate = min(coverage, freshness, conflict, provenance)`.

**Rust signature**
```rust
pub fn lens_aggregate(q: &LensQuality) -> Permille;
```

---

## Algorithm 14 — HITL-EVI calculation

See Q15 for the full model.

**Rust signature**
```rust
pub fn hitl_evi_ms(receipt: &WorkReceipt, risk: RiskScore, policy: &dyn Policy) -> HitlDecision;
```

---

## Algorithm 15 — Strategy trigger matching

See Q13 for the deterministic matching algorithm.

**Rust signature**
```rust
pub fn match_strategies(signals: &[Signal], library: &[Strategy]) -> Vec<StrategySuggestion>;
```

---

## Algorithm 16 — Work graph rollup + `workgraph_root`

See Q14 for semantics and construction order.

**Rust signature**
```rust
pub fn rollup_children(parent: &WorkReceipt, children: &[WorkReceipt]) -> OutcomeStatus;
pub fn compute_workgraph_root(parent_loop_id: LoopId, children: &[ChildEdge]) -> Hash256;
```

---

# 3. Merkle root formulas and domain separators

All roots are in `receipt.integrity.roots`.

## 3.1 `event_log_root` (T=EVENTLOG)

**Leaves** (ordered by `seq` ascending):
- `Lᵢ = CJ({ "seq": i, "event_hash": hex(event_hashᵢ) })`

`event_log_root = merkle_root(T=EVENTLOG, leaves=Lᵢ)`

## 3.2 `artifacts_root` (T=ARTIFACTS)

**Leaves** (order = all inputs then all outputs; each sublist sorted by `(path, sha256)`):
- Input leaf: `CJ({ "io":"in",  "path": path, "sha256": hex(hash) })`
- Output leaf: `CJ({ "io":"out", "path": path, "sha256": hex(hash) })`

## 3.3 `evidence_root` (T=EVIDENCE)

Evidence files are the subset of `manifest.files` whose `path` starts with `"evidence/"`.

**Leaves** (sorted by `path`):
- `CJ({ "path": path, "sha256": hex(file_sha256) })`

## 3.4 `lens_root` (T=LENS)

**Leaves** (sorted by `(kind, uri, sha256)`):
- `CJ({ "kind": kind, "uri": uri, "sha256": hex(sha), "ts_utc": ts, "provenance": prov })`

## 3.5 `effects_root` (T=EFFECTS)

**Leaves** (sorted by `(op, selector)`):
- `CJ({ "op": op, "selector": selector })`

## 3.6 `gates_root` (T=GATES)

**Leaves** (sorted by `(phase, gate_id)`):
- `CJ({ "phase": phase, "gate_id": id, "passed": bool, "evidence": path_or_null })`

## 3.7 `verification_root` (T=VERIFICATION)

**Leaves** (sorted by `(level, check_id)`):
- `CJ({ "level": level, "check_id": id, "passed": bool, "evidence": path_or_null })`

## 3.8 `workgraph_root` (T=WORKGRAPH)

**Leaves** (sorted by `spawn_index` ascending; spawn order, not completion order):
- `CJ({
    "spawn_index": i,
    "parent_loop_id": parent_loop_id,
    "child_loop_id": child_loop_id,
    "critical": critical,
    "child_proof_digest": hex(child_proof_digest)
})`

---

# 4. Canonicalization spec CJ-0.1

CJ-0.1 defines a canonical JSON byte format.

## 4.1 JSON subset

CJ-0.1 supports:
- `null`, `true`, `false`
- integers (no floats)
- strings (Unicode)
- arrays
- objects with string keys

It forbids:
- floating point numbers
- NaN/Infinity
- duplicate object keys

## 4.2 Encoding rules

- Output is UTF-8 bytes.
- No insignificant whitespace is permitted:
  - separators are exactly `,` and `:`
  - no spaces, tabs, or newlines
- Object keys are sorted **lexicographically by UTF-8 bytes** of the key string.
- Arrays preserve their existing order. (If an array is declared “MUST be sorted” in the schema, the producer MUST sort it before canonicalization.)

## 4.3 String escaping

Strings are enclosed in `"` and escape only:
- `"` as `\"`
- `\` as `\\`
- control chars `< 0x20` using:
  - `\b \f \n \r \t` where applicable
  - otherwise `\u00XX` (uppercase hex allowed but SHOULD be lowercase for producers)

Non-ASCII characters MUST be emitted as UTF-8 (not `\uXXXX`) except when required for control chars.

## 4.4 Integer formatting

- Base-10, no leading zeros (except `0`)
- Negative allowed (leading `-`)

---

# 5. FSM transition rules FSM-0.1

FSM states are phases: `Observe → Orient → Decide → Act → Verify → Lock`.

## 5.1 Allowed transitions

Let `P` be current phase.

### Forward progress
- Observe → Orient
- Orient → Decide
- Decide → Act
- Act → Verify
- Verify → Lock

### Repeats
- Observe → Observe (Repeat)
- Orient → Orient
- Decide → Decide
- Act → Act
- Verify → Verify
- Lock → Lock (only for waiting on HITL; must emit a HitlDecision or timeout)

### Backtracks (bounded)
- Decide → Orient
- Act → Decide
- Act → Orient
- Verify → Act
- Verify → Decide
- Verify → Orient

Backtrack to Observe is permitted only if explicitly requested by policy (e.g., missing signals).

### Spawn/join
- Spawn may occur in Decide or Act.
- Join is represented by `ChildJoined` events and/or by filling `children[]` in receipt.
- Parent MUST commit to children via `workgraph_root` once child digests are known.

## 5.2 Termination

A loop MUST end with:
- at least one `Lock` phase event, and
- a `Locked` payload event providing the final `Outcome` and `LockLevel`.

---

# 6. `verify_bundle` specification and failure codes

`verify_bundle(bundle_path, policy)` MUST perform the following in order.

## 6.1 Inputs

- `bundle_path`: directory containing `manifest.json`, `receipt.json`, `events.jsonl`.
- `policy`: a policy implementation matching `receipt.integrity.policy_id` and `policy_hash`.

## 6.2 Outputs

```rust
pub struct VerifyResult {
  pub ok: bool,
  pub proof_digest: Option<Hash256>,
  pub failures: Vec<VerifyFailure>,
}

pub struct VerifyFailure {
  pub code: VerifyFailCode,
  pub message: String,
}

pub enum VerifyFailCode {
  FILE_HASH_MISMATCH,
  RECEIPT_HASH_MISMATCH,
  EVENT_CHAIN_INVALID,
  ROOT_MISMATCH,
  PROOF_DIGEST_MISMATCH,
  FSM_INVALID,
  POLICY_VIOLATION,
  VERSION_UNSUPPORTED,
  EFFECT_BOUNDS_VIOLATION,
}
```

## 6.3 Step-by-step verification

### Step 0 — Load + parse
- Read `manifest.json`, `receipt.json`, `events.jsonl`
- Parse as JSON
- If parsing fails → `VERSION_UNSUPPORTED` (or a dedicated parse error)

### Step 1 — File hashing (manifest)
For every entry `f ∈ manifest.files`:
- Ensure `bundle_path/f.path` exists and is a regular file
- Recompute `sha256(file_bytes)` and compare to `f.sha256`
- If any mismatch → `FILE_HASH_MISMATCH`

> `manifest.json` itself is not included in `manifest.files` to avoid self-hashing recursion.

**Closure constraints (MUST):**
- `manifest.files` MUST include entries for `receipt.json` and `events.jsonl`.
- Every path referenced as `evidence` anywhere in:
  - receipt fields (`gates[].evidence`, `verification.results[].evidence`, `errors[].evidence`, `hitl[]`, etc.), and
  - event payloads (e.g., `SignalsCaptured.evidence`, `SkillExecuted.evidence`)
  MUST:
  1) exist on disk under the bundle directory, and  
  2) appear in `manifest.files`.

If any referenced evidence file is missing from disk or missing from `manifest.files`, verification MUST fail with `FILE_HASH_MISMATCH`.

### Step 2 — Version checks
- Verify `receipt.integrity.cj_version == "CJ-0.1"`, etc.
- If unsupported → `VERSION_UNSUPPORTED`

### Step 3 — Receipt hash check
- Compute `receipt_hash' = H( DS_RECEIPT || CJ(receipt WITHOUT integrity field) )`
- Compare to `receipt.integrity.receipt_hash`
- If mismatch → `RECEIPT_HASH_MISMATCH`

### Step 4 — Event chain check
- Parse each line of `events.jsonl` as `EventEnvelope`
- Verify `seq` starts at 0 and increments by 1
- Verify `prev_event_hash` / `event_hash` chain (Algorithm 2)
- If invalid → `EVENT_CHAIN_INVALID`

### Step 5 — Root recomputation
Recompute each root (Section 3) from:
- events (for `event_log_root`)
- receipt fields (for artifacts/lens/effects/gates/verification/workgraph)
- manifest evidence entries (for `evidence_root`)

Compare recomputed roots to `receipt.integrity.roots.*`.
If any mismatch → `ROOT_MISMATCH`.

### Step 6 — Proof digest check
- Compute `proof_digest'` (Algorithm 4)
- Compare to `receipt.integrity.proof_digest`
- If mismatch → `PROOF_DIGEST_MISMATCH`

### Step 7 — FSM trace check
- Validate phase trace (Algorithm 9)
- If invalid → `FSM_INVALID`

### Step 8 — Effect bounds check (policy-enabled)
If policy requires:
- Verify every observed effect is covered by declared effects (coverage relation defined in Section 11.Q11 + ENF-0.1).
- If violation → `EFFECT_BOUNDS_VIOLATION`.

### Step 9 — Policy compliance
Call `policy.verify_policy_compliance(receipt)`:
- Check required verifications exist and pass.
- Check HITL present if required.
- Check lock_level rules.
- If violation → `POLICY_VIOLATION`.

### Step 10 — Success
Return `ok=true` and `proof_digest`.

---

# 7. Property-based test specifications

All properties use randomized generation + shrinking. The goal is to prove invariants of hashing, FSM, normalization, and verification.

Generators MUST be seedable and deterministic (e.g., `proptest` with a fixed seed per run).

## 7.1 Properties (at least 20)

1. **CJ determinism:** `CJ(x)` is identical across repeated runs.  
2. **CJ object key ordering:** swapping insertion order of object keys does not change `CJ`.  
3. **Receipt hash stability:** `receipt_hash(strip_integrity(receipt))` unchanged if integrity block changes.  
4. **Event chain sensitivity:** changing any event payload byte changes `event_hash` and invalidates chain.  
5. **Event chain ordering:** swapping two events invalidates chain or changes root.  
6. **Merkle empty root stability:** empty list root equals `H(DS_EMPTY(T))` for all `T`.  
7. **Merkle permutation sensitivity:** permuting leaves changes root (except identical leaves).  
8. **Proof digest sensitivity:** changing any root or receipt_hash changes proof_digest.  
9. **Artifacts root sortedness:** permuting artifacts in receipt but then sorting yields same root.  
10. **Evidence root path sensitivity:** renaming evidence file changes evidence_root.  
11. **Lens freshness monotonic:** if all items get older (age_days increases), freshness does not increase.  
12. **Lens aggregate is min:** aggregate equals min components always.  
13. **Effect normalization idempotence:** `normalize(normalize(S)) == normalize(S)`.  
14. **Effect compression cap:** `|compress(S,K)| <= K`.  
15. **Effect compression coverage:** every original effect is covered by some compressed effect.  
16. **Strategy matching determinism:** same signals+library → same sorted suggestions.  
17. **Strategy matching threshold:** if all confidences < thresholds, no suggestions.  
18. **FSM legality:** randomly generated legal traces validate; illegal one-step mutations are rejected.  
19. **verify_bundle round trip:** building a bundle then verifying it succeeds.  
20. **verify_bundle tamper:** flipping 1 byte in any listed file fails with `FILE_HASH_MISMATCH`.  

## 7.2 Generator constraints

- UUIDs: random but valid.
- Timestamps: RFC3339 UTC, non-decreasing within event logs.
- `Permille`: uniform in 0..=1000.
- Effects: selectors drawn from canonical grammar.
- Work graphs: for v0.1, generate a tree with max depth D and max fanout F.

## 7.3 Test report JSON schema

See Section 12.

---

# 8. Golden bundle specifications (test vectors)

Golden bundles are committed fixtures with **exact expected `proof_digest`** values.

**Fixture path (repo):**
`workc_scenarios/fixtures/golden/v0.1/**`

Each fixture directory contains `bundle/` and must pass `verify_bundle`.

> The accompanying fixture zip (provided with this spec) contains these directories.

## 8.1 `basic_edit`

- Scenario: one file edit + regression check.
- Phase sequence: Observe → Orient → Decide → Act → Verify → Lock
- Expected `proof_digest`:
  - `11a092438552f1455bf9590a00e428b7a13b676cc87350a6d8d749e7aa34f29b`
- Expected result: `OK`

## 8.2 `verify_fail_backtrack`

- Scenario: verification fails once, backtracks, then passes.
- Phase sequence: Observe → Orient → Decide → Act → Verify → Orient → Decide → Act → Verify → Lock
- Expected `proof_digest`:
  - `a06657caf89502e8cafd4966bb170e5d898e8ffa2e9a7ce65f5dc0fb28673b8c`
- Expected result: `OK`

## 8.3 `parallel_children`

- Scenario: parent spawns 3 parallel child loops; all succeed.
- Expected **parent** `proof_digest`:
  - `9ca6104ddcb2c71354aed35faac67380d14f6b598cdc2d89c4a4ab3a50ce40e9`
- Expected child digests:
  - child_1: `0a2f4c29b443b890189690fa8f266c4dc00c7ceb920a8b371694fdb86004fc53`
  - child_2: `e119b01f3209cb889804acd1957e667f005c6b33556c5e7429fea25c118b85fd`
  - child_3: `7fc9ac4bbc6b17cf201aa732ad82149b492bd3c6ffcbd1c2fa16f10a26235595`
- Expected result: `OK` for parent and all children.

## 8.4 `effect_compression`

- Scenario: 200 atomic writes compressed to 50 effects.
- Expected `proof_digest`:
  - `4e6fb94d48b93c247f3df91c293e0d16b209ef368efb86c4fb7df36d580bf7d2`
- Expected result: `OK`

## 8.5 `hitl_checkpoint`

- Scenario: Committed lock with high-risk path requires human approval.
- Expected `proof_digest`:
  - `f3d2f2d2321364f2452ea88f3c4e07d710ac4085c0b29b3d75cac764eee417af`
- Expected result: `OK`

## 8.6 `strategy_applied`

- Scenario: Strategy STRAT-008 (Root Cause Loop) suggested and applied.
- Expected `proof_digest`:
  - `e04ce0f769a205f3629ee749d9a1733b06e624be9b1ac70b1082cdded75baf05`
- Expected result: `OK`

## 8.7 `tiered_recovery`

- Scenario: Recoverable error in Act is retried once; then success.
- Expected `proof_digest`:
  - `ab9ed30161d036d051bd91a940e2bd8404781688e3745fb496172330b2ff67a9`
- Expected result: `OK`

---

# 9. Benchmark specifications

Benchmarks must be runnable locally and in CI with fixed seeds.

## 9.1 Microbench targets (minimum)

1. **cj_canonicalize**  
   - Input: receipt-sized JSON (10KB, 100KB, 1MB)
   - Target: 100KB < 2ms on dev laptop (informational), CI budget may be higher.

2. **event_chain_verify**  
   - 10,000 events  
   - Target: < 50ms.

3. **merkle_root (10k leaves)**  
   - Target: < 100ms.

4. **verify_bundle**  
   - Bundle with 10k events + 1k evidence files  
   - Target: < 1s.

5. **effect_compress (2000 atomic → K=50)**  
   - Target: < 10ms.

## 9.2 Complexity expectations

- CJ: O(n) in bytes.
- Event chain verify: O(n) events.
- Merkle root: O(n) hashes (≈2n nodes).
- Effect compression: O(n log n) worst-case due to trie bookkeeping; typical O(n).

## 9.3 Bench report JSON schema

See Section 12.

---

# 10. Version compatibility matrix

| Spec | CJ | PROOF | FSM | ENF | Bundle |
|------|----|-------|-----|-----|--------|
| v0.1.0 | CJ-0.1 | PROOF-0.1 | FSM-0.1 | ENF-0.1 | BUNDLE-0.1 |
| v0.2.0 (planned) | CJ-0.1 | PROOF-0.2 | FSM-0.1 | ENF-0.2 | BUNDLE-0.1 |

**Rule:** A verifier MUST reject unknown `proof_version` with `VERSION_UNSUPPORTED`.

---

# 11. Answers to Q11–Q15 (mathematically rigorous)

## Q11. Effect Compression Trie Algorithm (ENF-0.1)

### Goal
Given a multiset of *atomic* effects `S` (after normalization), produce a compressed set `S'` such that:
1. `|S'| ≤ K`
2. **Coverage:** every `e ∈ S` is covered by some `e' ∈ S'`
3. Deterministic (no randomness)

### Effect coverage relation

Define coverage `covers(e', e)` per op:

- For `WriteFS` and `ReadFS`:
  - selectors are canonical paths prefixed by `"fs:"`.
  - Let `p'` be the selector path for `e'`, `p` for `e`.
  - `covers(e', e)` iff:
    - `e'.op == e.op`, and
    - either `p' == p` (exact file) OR `p'` ends with `/` and is a prefix of `p` in path-segment terms.

- For `Network`:
  - selectors `"net:{scheme}://{host}/{path...}"`
  - `covers` iff same scheme+host and prefix path coverage (directory-style `/` prefix).

- For `Exec` and `Publish` in v0.1:
  - coverage is equality (coarse selectors). (You may later add prefix semantics.)

### TrieMerge-v0.1 (deterministic)

Partition effects by `op`. Compress each op independently (then concatenate results; if still >K, compress again with cross-op policy weights).

For a fixed `op`, build a trie over selector segments.

For FS selectors:
- strip `"fs:"`
- split by `/` into segments, **preserving file names**
- directory-prefix selectors end with `/` and represent internal trie nodes

#### Candidate merge
A merge candidate is a trie node `p` whose set of **currently selected** children is `C(p)` and `|C(p)| ≥ 2`.

Merging `C(p)` into `p` reduces selected count by:
- `Δ(p) = |C(p)| - 1`

#### Cost function
Let `depth(x)` be segment depth (root depth 0).

Define:
- `depth_loss_sum(p) = Σ_{c∈C(p)} (depth(c) - depth(p))`
- `merge_cost(p) = w1 * depth_loss_sum(p) + w2 * Δ(p)`

Default weights (v0.1):
- `w1 = 10` (penalize loss of precision)
- `w2 = 1`  (small penalty per merge)

We choose the merge that minimizes the **ratio**:
- `ratio(p) = merge_cost(p) / Δ(p)`

Comparison without floats:
- `p < q` if `merge_cost(p) * Δ(q) < merge_cost(q) * Δ(p)`

Tie-breakers (in order):
1. lexicographically smallest parent selector string
2. smallest `op` enum discriminant

#### Algorithm
```text
selected = all leaf nodes representing atomic effects
while |selected| > K:
  candidates = { p | |C(p)| >= 2 }
  pick p* with minimal ratio(p*) under tie-breakers
  selected = (selected - C(p*)) ∪ {p*}
return selectors(selected) as S'
```

This terminates because each merge strictly reduces |selected|.

### Worked example (10 file writes, K=5)

Atomic write effects (paths):
1. src/auth/login.rs
2. src/auth/logout.rs
3. src/auth/session.rs
4. src/db/mod.rs
5. src/db/migrate.rs
6. src/db/query.rs
7. tests/auth_test.rs
8. tests/db_test.rs
9. README.md
10. Cargo.toml

Trie merges (intuitively optimal):
- Merge (1,2,3) → fs:src/auth/
- Merge (4,5,6) → fs:src/db/
- Merge (7,8)   → fs:tests/

Result set (5):
- fs:src/auth/
- fs:src/db/
- fs:tests/
- fs:README.md
- fs:Cargo.toml

Coverage holds because each original path is under one of these prefixes or equals.

---

## Q12. Lens Freshness Scoring (integer-only, weighted median)

Let `age_days(d)` be an integer number of days since the lens item timestamp:
- `d = floor((now_utc - ts_utc) / 86400 seconds)`

### Piecewise freshness map `f(d)` → permille

```
if d <= 7:        f(d) = 1000
if 8 <= d <= 30:  f(d) = 1000 - floor(300*(d-7)/23)
if 31<= d <=180:  f(d) = 700  - floor(500*(d-30)/150)
if d > 180:       f(d) = 100
```

Boundary checks:
- `f(7)=1000`
- `f(30)=700`
- `f(180)=200`

### Aggregate freshness via weighted median

Each lens item `i` has:
- score `sᵢ = f(dᵢ)`
- weight `wᵢ` where:
  - if `LensItem.weight` present use it
  - else default `wᵢ = 1000`

Compute weighted median:
1. Sort items by `sᵢ` ascending.
2. Let `W = Σ wᵢ`.
3. Let `c=0`. Scan in sorted order:
   - `c += wᵢ`
   - if `2c >= W`, return `sᵢ`.

If `W=0` (no items), freshness is 0.

---

## Q13. Strategy Trigger Matching (deterministic)

Signals:
```rust
pub struct Signal {
  pub name: String,
  pub confidence: Permille,
  pub evidence: Option<String>,
}
```

A strategy has triggers (OR in v0.1):
`triggers = [t1, t2, ...]`

### Trigger match scaling

For trigger `t` with threshold `θ` and signal confidence `c`:

- If `c < θ`: `m = 0`
- Else: scale above threshold:
  - `m = floor( 1000 * (c - θ) / (1000 - θ) )`

Apply trigger weight `w` (default 1000):
- `m_w = floor(m * w / 1000)`

### Strategy match

`match(strategy) = max_t m_w(t)`

If `match > 0`, emit a `StrategySuggestion`.

### Ordering and tie-break

Sort suggestions by:
1. `match_permille` descending
2. `strategy_id` lex ascending

Explanation MUST list matched signals in lex order and include values `(c, θ, m_w)`.

---

## Q14. Work Graph Rollup Semantics + workgraph_root order

### Rollup semantics

Let parent have own intrinsic outcome `O_self`.
Let children edges be `E = {e1..en}` with `critical` flag and child outcome.

Define severity order:
`success < partial < failed`.

Compute child rollup outcome `O_child`:

1. If any critical child is `failed` → `O_child = failed`
2. Else if any critical child is `partial` → `O_child = partial`
3. Else if any non-critical child is not `success` → `O_child = partial`
4. Else `O_child = success`

Final parent outcome:
`O_parent = max_severity(O_self, O_child)`

### workgraph_root construction order

Leaves MUST be in **spawn order**:
- sort by `spawn_index` ascending (0..n-1)

Leaf bytes:
`CJ({spawn_index, parent_loop_id, child_loop_id, critical, child_proof_digest})`

Root computed by MRKL-0.1 with `T=WORKGRAPH`.

---

## Q15. HITL-EVI calibration (exact model)

We require HITL when:

`p_override * L_loss > C_cost`

All quantities are deterministic.

### Units

- `p_override_permille ∈ [0,1000]`
- `L_loss_ms ∈ u64` (expected remediation time if agent proceeds incorrectly)
- `C_cost_ms ∈ u64` (human interruption time)

Decision rule (integer-only):
`require_hitl` iff:

`(p_override_permille * L_loss_ms) > (1000 * C_cost_ms)`

Compute:
`EVI_ms = floor(p_override_permille * L_loss_ms / 1000) - C_cost_ms`

### p_override model (logit approximation)

Let features `x_j` in permille units unless noted.

| Feature | Symbol | Range | Meaning |
|---|---:|---:|---|
| Bias | 1 | 1 | intercept |
| Lock level weight | x1 | 0..1000 | Draft=0, Staged=200, Committed=600, Published=850, Immutable=1000 |
| Publish present | x2 | 0/1000 | any `EffectOp::Publish` |
| Network present | x3 | 0/1000 | any `EffectOp::Network` |
| Lens deficit | x4 | 0..1000 | `1000 - lens.quality.aggregate` |
| Verify failed recently | x5 | 0/1000 | any failed check prior to lock |

Coefficients `β` in “milli-logit”:
- `β0 = -3000`
- `β1 =  4000`
- `β2 =  2500`
- `β3 =  1800`
- `β4 =  2000`
- `β5 =  2200`

Compute:
`z_milli = β0 + floor(β1*x1/1000) + floor(β2*x2/1000) + ...`

Approximate sigmoid in permille (deterministic):
- `p_permille = clamp(0,1000, 500 + floor( z_milli * 1000 / (4000 + |z_milli|) ))`

### Default fatigue cost

`C_cost_ms` default = **45,000 ms** (45 seconds) in v0.1.

Policy MAY adjust by user preferences and recent checkpoint frequency.

---

# 12. JSON schemas

These schemas are used by the testkit and CI artifacts.

## 12.1 `test_report.json` schema (Draft 2020-12)

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "Motus Test Report",
  "type": "object",
  "required": ["spec_version", "cj_version", "proof_version", "fsm_version", "enf_version", "seed", "properties", "goldens"],
  "properties": {
    "spec_version": {"type": "string"},
    "cj_version": {"type": "string"},
    "proof_version": {"type": "string"},
    "fsm_version": {"type": "string"},
    "enf_version": {"type": "string"},
    "seed": {"type": "string"},
    "properties": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["name", "passed"],
        "properties": {
          "name": {"type": "string"},
          "passed": {"type": "boolean"},
          "cases": {"type": "integer", "minimum": 0},
          "failures": {"type": "integer", "minimum": 0},
          "notes": {"type": "string"}
        }
      }
    },
    "goldens": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["name", "passed", "expected_proof_digest"],
        "properties": {
          "name": {"type": "string"},
          "passed": {"type": "boolean"},
          "expected_proof_digest": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
          "actual_proof_digest": {"type": "string", "pattern": "^[0-9a-f]{64}$"}
        }
      }
    }
  }
}
```

## 12.2 `bench_report.json` schema (Draft 2020-12)

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "Motus Benchmark Report",
  "type": "object",
  "required": ["spec_version", "machine", "benches"],
  "properties": {
    "spec_version": {"type": "string"},
    "machine": {
      "type": "object",
      "required": ["os", "cpu", "ram_gb"],
      "properties": {
        "os": {"type": "string"},
        "cpu": {"type": "string"},
        "ram_gb": {"type": "number", "minimum": 0}
      }
    },
    "benches": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["name", "n", "time_ms"],
        "properties": {
          "name": {"type": "string"},
          "n": {"type": "integer", "minimum": 0},
          "time_ms": {"type": "number", "minimum": 0},
          "notes": {"type": "string"}
        }
      }
    }
  }
}
```

---
