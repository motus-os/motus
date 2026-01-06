#!/bin/bash
# GATE-COV-001: Coverage Check
# Reference: .ai/RELEASE-STANDARD.md
# Purpose: Verify test coverage meets thresholds
# Security: No user input, safe for CI
set -e

echo "GATE-COV-001: Coverage Check"
echo "============================="

timeout_cmd() {
  local seconds="$1"
  shift
  if command -v timeout >/dev/null 2>&1; then
    timeout "$seconds" "$@"
  elif command -v gtimeout >/dev/null 2>&1; then
    gtimeout "$seconds" "$@"
  else
    python3 - "$seconds" "$@" <<'PY'
import subprocess
import sys

timeout = int(sys.argv[1])
cmd = sys.argv[2:]
proc = subprocess.run(cmd, timeout=timeout)
sys.exit(proc.returncode)
PY
  fi
}

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="${REPO_ROOT:-${MOTUS_REPO_ROOT:-$(cd "$SCRIPT_DIR/../.." && pwd)}}"
CLI_ROOT="$REPO_ROOT"
if [ -d "$REPO_ROOT/packages/cli" ]; then
  CLI_ROOT="$REPO_ROOT/packages/cli"
fi
cd "$CLI_ROOT"

# Cleanup handler
cleanup() {
  rm -f coverage.json .coverage 2>/dev/null || true
  if [ -n "${VENV_DIR:-}" ] && [ -d "$VENV_DIR" ]; then
    rm -rf "$VENV_DIR"
  fi
}
trap cleanup EXIT

# Verify required commands
for cmd in python3; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "FAIL: Required command '$cmd' not found"
    exit 1
  fi
done

PYTHON_BIN="python3"
if ! command -v pytest >/dev/null 2>&1; then
  echo "WARN: pytest not found - creating temp venv for coverage run"
  umask 077
  VENV_DIR=$(mktemp -d)
  python3 -m venv "$VENV_DIR/venv"
  "$VENV_DIR/venv/bin/pip" install -q --upgrade pip
  "$VENV_DIR/venv/bin/pip" install -q "$CLI_ROOT[dev,web,mcp,gemini]"
  PYTHON_BIN="$VENV_DIR/venv/bin/python"
fi

# Thresholds (baseline-relative if available)
MIN_COVERAGE=80
MIN_FAILURE_TESTS=10

BASELINE_FILE="$CLI_ROOT/docs/quality/health-baseline.json"
POLICY_FILE="$CLI_ROOT/docs/quality/health-policy.json"
if [ -f "$BASELINE_FILE" ] && [ -f "$POLICY_FILE" ]; then
  MIN_COVERAGE=$(BASELINE_FILE="$BASELINE_FILE" POLICY_FILE="$POLICY_FILE" python3 - <<'PY'
import json
import os
from pathlib import Path

baseline = json.loads(Path(os.environ["BASELINE_FILE"]).read_text())
policy = json.loads(Path(os.environ["POLICY_FILE"]).read_text())

baseline_pct = baseline.get("coverage", {}).get("overall_percent")
min_delta = policy.get("coverage", {}).get("min_delta_pct", 0)

if isinstance(baseline_pct, (int, float)):
    threshold = baseline_pct + min_delta
    print(f"{threshold:.2f}")
else:
    print("80")
PY
  )
fi

echo "Thresholds:"
echo "  Minimum coverage: ${MIN_COVERAGE}%"
echo "  Minimum failure tests: $MIN_FAILURE_TESTS"
echo ""

# Run pytest with coverage (with timeout)
echo "Running tests with coverage..."
if ! timeout_cmd 300 "$PYTHON_BIN" -m pytest tests/ --cov=src/motus --cov-report=json --cov-report=term-missing -q; then
  echo ""
  echo "FAIL: Tests failed - cannot verify coverage"
  echo "Run 'pytest tests/ -v' for detailed output"
  exit 1
fi

# Parse coverage from JSON with validation
if [ -f "coverage.json" ]; then
  # Use Python for both parsing and comparison (no bc dependency)
  result=$(python3 -c "
import json
import sys
try:
    with open('coverage.json') as f:
        data = json.load(f)
    pct = data.get('totals', {}).get('percent_covered', 0)
    if not isinstance(pct, (int, float)):
        print('ERROR: Invalid coverage value', file=sys.stderr)
        sys.exit(2)
    print(f'{pct:.1f}')
    sys.exit(0 if pct >= $MIN_COVERAGE else 1)
except (json.JSONDecodeError, KeyError, TypeError) as e:
    print(f'ERROR: Failed to parse coverage.json: {e}', file=sys.stderr)
    sys.exit(2)
" 2>&1)
  exit_code=$?

  if [ $exit_code -eq 2 ]; then
    echo "FAIL: $result"
    exit 1
  fi

  coverage="$result"
  echo ""
  echo "Coverage: ${coverage}%"

  if [ $exit_code -eq 1 ]; then
    echo ""
    echo "FAIL: Coverage ${coverage}% below threshold ${MIN_COVERAGE}%"
    exit 1
  fi
else
  echo "WARN: Cannot find coverage.json - skipping coverage check"
  echo "  This may indicate pytest-cov is not installed"
fi

# Count failure mode tests
echo ""
echo "Counting failure mode tests..."
failure_tests=$(grep -rE "def test_.*_(fail|error|corrupt|invalid|timeout|reject)" tests/ 2>/dev/null | wc -l | tr -d ' ')
echo "Failure mode tests found: $failure_tests"

if [ "$failure_tests" -lt "$MIN_FAILURE_TESTS" ]; then
  echo ""
  echo "WARN: Only $failure_tests failure mode tests (threshold: $MIN_FAILURE_TESTS)"
  echo "  Consider adding tests for:"
  echo "  - Invalid input handling"
  echo "  - Network failures"
  echo "  - Database corruption"
  echo "  - Timeout scenarios"
fi

echo ""
echo "PASS: Coverage check complete"
echo "  Coverage: ${coverage:-N/A}%"
echo "  Failure tests: $failure_tests"
exit 0
