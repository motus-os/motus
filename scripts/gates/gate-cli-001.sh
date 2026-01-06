#!/bin/bash
# GATE-CLI-001: Command Smoke Test
# Purpose: Verify all documented commands are available and respond
# Security: No user input, safe for CI
set -e

echo "=== GATE-CLI-001: Command Smoke Test ==="

# Verify motus command exists
if ! command -v motus >/dev/null 2>&1; then
  echo "FAIL: motus command not found"
  echo "  Install with: pip install motusos"
  exit 1
fi

# Core commands that must exist and respond to --help
commands=(
  "list"
  "show"
  "feed"
  "web"
  "doctor"
  "db"
  "release"
  "work"
  "roadmap"
  "policy"
  "claims"
  "activity"
  "health"
)

failed=0
passed=0

for cmd in "${commands[@]}"; do
  if motus "$cmd" --help >/dev/null 2>&1; then
    echo "  [OK] motus $cmd"
    passed=$((passed + 1))
  else
    echo "  [FAIL] motus $cmd"
    failed=$((failed + 1))
  fi
done

echo ""
echo "Results: $passed passed, $failed failed"

if [ $failed -gt 0 ]; then
  echo ""
  echo "FAIL: $failed command(s) not available"
  echo ""
  echo "Possible causes:"
  echo "  1. Package conflict (run gate-pkg-001.sh first)"
  echo "  2. Command not registered in dispatch.py"
  echo "  3. Import error in command module"
  exit 1
fi

echo ""
echo "PASS: All ${#commands[@]} commands verified"
