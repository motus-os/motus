#!/bin/bash
# GATE-SEC-003: Bandit security scan
# Purpose: Static analysis for common Python security issues
# Security: Fail-closed if bandit is missing or findings exist
set -e

echo "GATE-SEC-003: Bandit security scan"
echo "================================="

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="${REPO_ROOT:-${MOTUS_REPO_ROOT:-$(cd "$SCRIPT_DIR/../.." && pwd)}}"
TARGET_DIR="${1:-$REPO_ROOT/packages/cli/src}"

if [ ! -d "$TARGET_DIR" ]; then
  echo "FAIL: Target directory not found: $TARGET_DIR"
  exit 1
fi

if ! command -v bandit >/dev/null 2>&1; then
  echo "FAIL: bandit is not installed"
  echo "Install with: pip install bandit"
  exit 1
fi

report_path="/tmp/bandit.json"
bandit -r "$TARGET_DIR" -f json -o "$report_path"

if [ ! -s "$report_path" ]; then
  echo "FAIL: bandit report missing or empty"
  exit 1
fi

echo "PASS: bandit scan complete"
exit 0
