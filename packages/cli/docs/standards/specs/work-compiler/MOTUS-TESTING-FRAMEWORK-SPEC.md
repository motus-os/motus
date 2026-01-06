# Motus Testing + Benchmarking Framework Spec

**Source**: GPT Pro
**Date**: 2025-12-24
**Status**: Complete, ready for implementation

---

## Overview

Implementation-ready Rust testing + benchmarking framework for Motus Work Compiler.

**Core Principle**: Everything flows through one oracle: `verify_bundle(bundle) -> Verdict { PASS | FAIL + reasons }`

---

## 1) Workspace Layout

```
workc_core/           # Kernel: types, CJ-0.1, PROOF-0.1, FSM, verify_bundle()
workc_runtime/        # Motus adapters (Lens, Skills, Gates, Coordination)
workc_cli/            # CLI: run, verify-bundle, bench, explain
workc_testkit/        # Deterministic testing harness (NEW)
workc_scenarios/      # Scenario suites (NEW)
workc_bench/          # Benchmarks (NEW)
workc_loom/           # Concurrency model-checking (optional)
```

---

## 2) workc_testkit Crate

### Module Layout

```
workc_testkit/src/
  lib.rs
  clock.rs          # FakeClock
  rng.rs            # SeededRng
  scripts.rs        # LensScript, PlanScript, etc.
  sim_runtime.rs    # SimRuntime (deterministic Services impl)
  scenario.rs       # Scenario struct
  runner.rs         # ScenarioRunner
  golden.rs         # GoldenBundle fixtures
  tamper.rs         # TamperMutator
  report.rs         # TestReport, BenchReport
  assertions.rs     # assert_bundle_pass!, assert_bundle_fail_codes!
```

### Dependencies

```toml
[dependencies]
serde = { version = "1", features = ["derive"] }
serde_json = "1"
uuid = { version = "1", features = ["serde", "v4"] }
time = { version = "0.3", features = ["serde", "formatting"] }
sha2 = "0.10"
hex = "0.4"
thiserror = "2"
schemars = "0.8"
tempfile = "3"
```

---

## 3) Deterministic Clock + RNG

### clock.rs

```rust
use time::OffsetDateTime;

pub trait Clock: Send + Sync {
    fn now_utc(&self) -> OffsetDateTime;
}

#[derive(Clone)]
pub struct FakeClock {
    now: OffsetDateTime,
    step_ms: i64,
}

impl FakeClock {
    pub fn new(start: OffsetDateTime, step_ms: i64) -> Self { Self { now: start, step_ms } }
    pub fn advance(&mut self) { self.now += time::Duration::milliseconds(self.step_ms); }
}

impl Clock for FakeClock {
    fn now_utc(&self) -> OffsetDateTime { self.now }
}
```

### rng.rs

```rust
#[derive(Clone)]
pub struct SeededRng(u64);

impl SeededRng {
    pub fn new(seed: u64) -> Self { Self(seed) }
    pub fn next_u64(&mut self) -> u64 {
        // xorshift64*
        let mut x = self.0;
        x ^= x >> 12;
        x ^= x << 25;
        x ^= x >> 27;
        self.0 = x;
        x.wrapping_mul(2685821657736338717u64)
    }
}
```

---

## 4) Script Types

### scripts.rs

```rust
use serde::{Serialize, Deserialize};

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct LensItem {
    pub key: String,
    pub value: String,
    pub source: String,
    pub ts_utc: String,
    pub sha256: String,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct LensScript {
    pub items: Vec<LensItem>,
    pub quality_override: Option<LensQuality>,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct LensQuality {
    pub coverage_permille: u16,
    pub freshness_permille: u16,
    pub conflict_permille: u16,
    pub provenance_permille: u16,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct PlanScript {
    pub steps: Vec<PlanStepScript>,
    pub complex_decompose: Option<Vec<IntentScript>>,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct IntentScript {
    pub description: String,
    pub source: String,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct PlanStepScript {
    pub name: String,
    pub resources: Vec<String>,
    pub effects: Vec<EffectScript>,
    pub action: ActionScript,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub enum ActionScript {
    WriteFile { path: String, contents_sha256: String },
    ReadFile { path: String },
    Exec { program: String, argv: Vec<String> },
    Network { host: String, path: String },
    Publish { destination: String },
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct EffectScript {
    pub op: String,
    pub selector: String,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct GateScript {
    pub pre: Vec<GateDecision>,
    pub post: Vec<GateDecision>,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct GateDecision {
    pub at_step: usize,
    pub pass: bool,
    pub code: String,
    pub message: String,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct VerifyScript {
    pub results: Vec<CheckScript>,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct CheckScript {
    pub check: String,
    pub pass: bool,
    pub evidence_path: String,
    pub evidence_sha256: String,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct CoordScript {
    pub conflicts: Vec<LockConflict>,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct LockConflict {
    pub resource: String,
    pub on_claim_n: usize,
    pub resolution: ConflictResolution,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub enum ConflictResolution {
    WaitThenAcquire { wait_ms: u64 },
    Fail { code: String, message: String },
    ForceReleaseThenAcquire,
}
```

---

## 5) Scenario + SimRuntime

### scenario.rs

```rust
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Scenario {
    pub id: String,
    pub description: String,
    pub seed: u64,
    pub intent: IntentScript,
    pub lens: LensScript,
    pub plan: PlanScript,
    pub gates: GateScript,
    pub verify: VerifyScript,
    pub coord: CoordScript,
    pub expect: Expectations,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Expectations {
    pub expect_outcome_status: String,
    pub expect_bundle_verdict: String,
    pub expect_failure_codes: Vec<String>,
    pub max_retries: Option<u32>,
    pub must_backtrack_on_verify_fail: bool,
    pub must_require_human_approval: bool,
}
```

### sim_runtime.rs

```rust
pub struct SimRuntime<C: Clock> {
    pub clock: C,
    pub rng: SeededRng,
    pub lens: LensScript,
    pub plan: PlanScript,
    pub gates: GateScript,
    pub verify: VerifyScript,
    pub coord: CoordScript,
    pub mem: SimMemory,
}

pub struct SimMemory {
    pub evidence_files: BTreeMap<String, Vec<u8>>,
    pub artifacts: BTreeMap<String, Vec<u8>>,
}
```

---

## 6) Tamper Suite

### tamper.rs

```rust
#[derive(Clone, Debug, Serialize, Deserialize)]
pub enum TamperOp {
    FlipByte { rel_path: String, offset: usize, xor: u8 },
    DeleteFile { rel_path: String },
    TruncateFile { rel_path: String, new_len: usize },
    ReplaceBytes { rel_path: String, offset: usize, bytes_hex: String },
    ReorderEvents { swap_i: usize, swap_j: usize },
    ModifyReceiptField { json_pointer: String, new_json: serde_json::Value },
    CorruptManifestHash { entry_path: String, new_sha256: String },
}

pub struct TamperMutator;

impl TamperMutator {
    pub fn apply(bundle_dir: &Path, op: &TamperOp) -> anyhow::Result<()> { ... }
}
```

---

## 7) Failure Codes (Stable)

```rust
pub enum VerifyFailCode {
    HASH_MISMATCH,
    MANIFEST_MISSING_FILE,
    MERKLE_MISMATCH_ARTIFACTS,
    MERKLE_MISMATCH_EVIDENCE,
    EVENT_CHAIN_MISMATCH,
    RECEIPT_HASH_MISMATCH,
    PROOF_DIGEST_MISMATCH,
    FSM_ILLEGAL_TRANSITION,
    POLICY_VIOLATION,
    VERSION_UNSUPPORTED,
}
```

---

## 8) Report Schemas

### TestReport

```rust
#[derive(Clone, Debug, Serialize, Deserialize, JsonSchema)]
pub struct TestReport {
    pub schema_version: String,  // "workc-test-report-0.1"
    pub run_id: String,
    pub time_utc: String,
    pub duration_ms: u64,
    pub git: GitInfo,
    pub platform: PlatformInfo,
    pub summary: TestSummary,
    pub suites: Vec<SuiteResult>,
    pub scenarios: Vec<ScenarioResult>,
}

#[derive(Clone, Debug, Serialize, Deserialize, JsonSchema)]
pub struct TestSummary {
    pub total: u32,
    pub passed: u32,
    pub failed: u32,
    pub skipped: u32,
}

#[derive(Clone, Debug, Serialize, Deserialize, JsonSchema)]
pub struct ScenarioResult {
    pub scenario_id: String,
    pub description: String,
    pub bundle: BundlePaths,
    pub expected_outcome_status: String,
    pub actual_outcome_status: String,
    pub verify_ok: bool,
    pub proof_digest: Option<String>,
    pub failures: Vec<FailureRecord>,
    pub metrics: ScenarioMetrics,
}

#[derive(Clone, Debug, Serialize, Deserialize, JsonSchema)]
pub struct ScenarioMetrics {
    pub wall_ms: u64,
    pub steps: u32,
    pub retries: u32,
    pub backtracks: u32,
    pub child_loops: u32,
    pub verify_checks: u32,
    pub hitl_prompts: u32,
}
```

### BenchReport

```rust
#[derive(Clone, Debug, Serialize, Deserialize, JsonSchema)]
pub struct BenchReport {
    pub schema_version: String,  // "workc-bench-report-0.1"
    pub run_id: String,
    pub time_utc: String,
    pub git: GitInfo,
    pub platform: PlatformInfo,
    pub micro: Vec<MicroBenchResult>,
    pub macro_suites: Vec<MacroSuiteResult>,
}

#[derive(Clone, Debug, Serialize, Deserialize, JsonSchema)]
pub struct MicroBenchResult {
    pub name: String,
    pub unit: String,
    pub samples: u32,
    pub p50: f64,
    pub p95: f64,
    pub p99: f64,
    pub mean: f64,
    pub stddev: f64,
}

#[derive(Clone, Debug, Serialize, Deserialize, JsonSchema)]
pub struct MacroSuiteResult {
    pub suite: String,
    pub scenarios: u32,
    pub pass_rate_permille: u16,
    pub lock_latency_ms_p50: u64,
    pub lock_latency_ms_p95: u64,
    pub verify_latency_ms_p50: u64,
    pub verify_latency_ms_p95: u64,
    pub events_per_sec_p50: f64,
    pub evidence_bytes_total: u64,
    pub artifacts_count_total: u64,
    pub hitl_prompts_total: u64,
}
```

---

## 9) Golden Bundle Layout

```
workc_scenarios/fixtures/golden/
  v0.1/
    basic_success/
      bundle/
        receipt.json
        events.jsonl
        manifest.json
        evidence/...
    verify_fail_backtrack/
      bundle/...
    parallel_children_coordination/
      bundle/...
```

---

## 10) CI Pipeline

```yaml
jobs:
  - cargo fmt --check
  - cargo clippy -- -D warnings
  - cargo test -p workc_core
  - cargo test -p workc_testkit
  - cargo test -p workc_scenarios
  - workc verify-bundle workc_scenarios/fixtures/golden/v0.1/*/bundle

nightly:
  - cargo bench -p workc_bench
  - workc bench suite_core --json out/bench_report.json
```

---

## 11) Minimum Test Suites

1. `suite_smoke` - Fast, always runs
2. `suite_core` - 10 workmark scenarios
3. `suite_parallel` - Recursion + coordination
4. `suite_tamper` - Adversarial validation
5. `suite_versioning` - Old bundles remain verifiable

---

*Complete testing framework spec. Ready for implementation.*
