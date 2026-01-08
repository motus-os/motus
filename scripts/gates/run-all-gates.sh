#!/bin/bash
# run-all-gates.sh: Execute all release gates in sequence
# Purpose: Single command to verify release readiness
# Usage: ./scripts/gates/run-all-gates.sh
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${MOTUS_REPO_ROOT:-$(cd "$SCRIPT_DIR/../.." && pwd)}"

if [ ! -d "$REPO_ROOT/packages/cli" ] && [ ! -f "$REPO_ROOT/pyproject.toml" ]; then
  echo "FAIL: MOTUS_REPO_ROOT is not set to a valid repo."
  echo "Set MOTUS_REPO_ROOT to the canonical repo (e.g., /Users/ben/GitHub/motus)."
  exit 1
fi

cd "$REPO_ROOT"
export REPO_ROOT

echo "=============================================="
echo "  MOTUS RELEASE GATES"
echo "  $(date)"
echo "=============================================="
echo ""

failed_gates=()
passed_gates=()

run_gate() {
  local gate_name=$1
  local gate_script=$2
  shift 2

  echo "----------------------------------------------"
  echo "Running: $gate_name"
  echo "----------------------------------------------"

  if [ -x "$gate_script" ]; then
    if "$gate_script" "$@"; then
      passed_gates+=("$gate_name")
      echo ""
    else
      failed_gates+=("$gate_name")
      echo ""
      echo "^^^ GATE FAILED: $gate_name ^^^"
      echo ""
    fi
  else
    echo "SKIP: Script not found or not executable: $gate_script"
    echo ""
  fi
}

# Run gates in dependency order (fail-closed: any failure blocks release)

# Phase 1: Environment checks
echo ""
echo "=== Phase 1: Environment Checks ==="
run_gate "GATE-PKG-001" "$SCRIPT_DIR/gate-pkg-001.sh"
run_gate "GATE-REPO-001" "$SCRIPT_DIR/gate-repo-001.sh"
run_gate "GATE-DB-001" "$SCRIPT_DIR/gate-db-001.sh"
run_gate "GATE-DB-002" "$SCRIPT_DIR/gate-db-002.sh"
run_gate "GATE-ROADMAP-001" "$SCRIPT_DIR/gate-roadmap-001.sh"

# Phase 2: Functionality checks
echo ""
echo "=== Phase 2: Functionality Checks ==="
run_gate "GATE-CLI-001" "$SCRIPT_DIR/gate-cli-001.sh"
run_gate "GATE-WEB-001" "$SCRIPT_DIR/gate-web-001.sh"
run_gate "GATE-COV-001" "$SCRIPT_DIR/gate-cov-001.sh"
run_gate "GATE-PERF-001" "$SCRIPT_DIR/gate-perf-001.sh"

# Phase 3: Security checks
echo ""
echo "=== Phase 3: Security Checks ==="
run_gate "GATE-SEC-002" "$SCRIPT_DIR/gate-sec-002.sh"
run_gate "GATE-SEC-003" "$SCRIPT_DIR/gate-sec-003.sh"
run_gate "GATE-DEP-002" "$SCRIPT_DIR/gate-dep-002.sh"
run_gate "GATE-SRC-001" "$SCRIPT_DIR/gate-src-001.sh"
run_gate "GATE-PATH-001" "$SCRIPT_DIR/gate-path-001.sh"
run_gate "GATE-MIG-001" "$SCRIPT_DIR/gate-migrations-001.sh"
run_gate "GATE-PKG-002" "$SCRIPT_DIR/gate-pkg-002.sh"
run_gate "GATE-PKG-003" "$SCRIPT_DIR/gate-pkg-003.sh"
run_gate "GATE-TEST-001" "$SCRIPT_DIR/gate-test-001.sh"

# Phase 4: Release validation (optional - pass version as arg)
# These are run during release, not every CI run
if [ "${RUN_RELEASE_GATES:-false}" = "true" ]; then
  echo ""
  echo "=== Phase 4: Release Validation ==="
  run_gate "GATE-INSTALL-001" "$SCRIPT_DIR/gate-install-001.sh"
  run_gate "GATE-FRESH-001" "$SCRIPT_DIR/gate-fresh-001.sh"
  run_gate "GATE-FRESH-002" "$SCRIPT_DIR/gate-fresh-002.sh"
  run_gate "GATE-UPGRADE-001" "$SCRIPT_DIR/gate-upgrade-001.sh" "${PREV_VERSION:-0.1.0}"
  run_gate "GATE-ROLLBACK-001" "$SCRIPT_DIR/gate-rollback-001.sh" "${CURRENT_VERSION:-}" "${PREV_VERSION:-}"
  run_gate "GATE-RELEASE-001" "$SCRIPT_DIR/gate-release-001.sh" "${CURRENT_VERSION:-}"
fi

# Summary
echo "=============================================="
echo "  SUMMARY"
echo "=============================================="
echo ""
echo "Passed: ${#passed_gates[@]}"
for gate in "${passed_gates[@]}"; do
  echo "  [PASS] $gate"
done

echo ""
echo "Failed: ${#failed_gates[@]}"
for gate in "${failed_gates[@]}"; do
  echo "  [FAIL] $gate"
done

echo ""
if [ ${#failed_gates[@]} -gt 0 ]; then
  echo "RELEASE BLOCKED: ${#failed_gates[@]} gate(s) failed"
  echo ""
  echo "Fix the failed gates before releasing."
  exit 1
else
  echo "ALL GATES PASSED"
  echo "Release may proceed."
  exit 0
fi
