#!/bin/bash
# GATE-TEST-001: Test Isolation Verification
# Reference: .ai/RELEASE-STANDARD.md
# Purpose: Verify tests use isolated environment, never touch user's ~/.motus
# Security: Prevents tests from corrupting user data or leaking test data to prod
set -e

echo "GATE-TEST-001: Test Isolation Verification"
echo "==========================================="

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Find test directory
TEST_DIR=""
for dir in "$REPO_ROOT/tests" "$REPO_ROOT/test" "$REPO_ROOT/packages/cli/tests"; do
  if [ -d "$dir" ]; then
    TEST_DIR="$dir"
    break
  fi
done

if [ -z "$TEST_DIR" ]; then
  echo "SKIP: No test directory found"
  exit 0
fi

echo "Test directory: $TEST_DIR"
echo ""

failures=0
warnings=0

# === Check 1: conftest.py sets database isolation ===
echo "=== Check 1: Test Fixture Isolation ==="

conftest_files=$(find "$TEST_DIR" -name "conftest.py" 2>/dev/null)
isolation_found=0

for conftest in $conftest_files; do
  # Check for MOTUS_DATABASE__PATH or tmp_path fixture usage
  if grep -qE "MOTUS_DATABASE__PATH|tmp_path|tmpdir|temp.*dir|HOME=.*tmp" "$conftest" 2>/dev/null; then
    echo "  [OK] $conftest has isolation patterns"
    isolation_found=1
  fi
done

if [ $isolation_found -eq 0 ]; then
  echo "  [WARN] No test isolation fixtures found"
  echo "         Tests should set MOTUS_DATABASE__PATH or HOME to temp directory"
  warnings=$((warnings + 1))
fi

# === Check 2: No direct ~/.motus access in tests ===
echo ""
echo "=== Check 2: No Direct Home Access ==="

# Patterns that indicate direct access to user's home
home_patterns=(
  "~/.motus"
  "\$HOME/.motus"
  "expanduser.*\.motus"
  "Path.home().*motus"
  "os.path.join.*HOME.*motus"
)

for pattern in "${home_patterns[@]}"; do
  # Exclude tests that are specifically testing path validation/security
  matches=$(grep -rniE "$pattern" "$TEST_DIR" --include="*.py" 2>/dev/null | \
    grep -v "conftest" | \
    grep -v "test_path" | \
    grep -v "test_security" | \
    grep -v "test_config.*assert" | \
    head -5)
  if [ -n "$matches" ]; then
    echo "  [WARN] Direct home directory access found:"
    echo "$matches" | sed 's/^/    /'
    echo "  (Review if these are testing path validation - if so, OK)"
    warnings=$((warnings + 1))
  fi
done

if [ $failures -eq 0 ]; then
  echo "  [OK] No direct home directory access"
fi

# === Check 3: Tests don't modify global state ===
echo ""
echo "=== Check 3: Global State Modification ==="

# Patterns that modify global state
global_patterns=(
  "os\.environ\[.*\]\s*="
  "sys\.path\.insert"
  "sys\.path\.append"
  "importlib\.reload"
  "patch\.dict.*environ"
)

global_found=0
for pattern in "${global_patterns[@]}"; do
  matches=$(grep -rniE "$pattern" "$TEST_DIR" --include="*.py" 2>/dev/null | head -3)
  if [ -n "$matches" ]; then
    # Filter out ones that are properly scoped (in fixtures or context managers)
    if echo "$matches" | grep -vqE "@pytest|with patch|@fixture"; then
      echo "  [WARN] Global state modification:"
      echo "$matches" | sed 's/^/    /'
      global_found=1
    fi
  fi
done

if [ $global_found -eq 0 ]; then
  echo "  [OK] No unscoped global state modification"
fi

# === Check 4: Tests clean up after themselves ===
echo ""
echo "=== Check 4: Cleanup Patterns ==="

# Look for temp file creation without cleanup
temp_patterns="tempfile\.|mktemp|NamedTemporaryFile|TemporaryDirectory"
temp_uses=$(grep -rcE "$temp_patterns" "$TEST_DIR" --include="*.py" 2>/dev/null | awk -F: '{sum+=$2} END {print sum+0}')
cleanup_patterns="cleanup|teardown|finally:|with.*temp|@pytest.fixture.*scope"
cleanup_uses=$(grep -rcE "$cleanup_patterns" "$TEST_DIR" --include="*.py" 2>/dev/null | awk -F: '{sum+=$2} END {print sum+0}')

echo "  Temp file operations: $temp_uses"
echo "  Cleanup patterns: $cleanup_uses"

if [ "$temp_uses" -gt 0 ] && [ "$cleanup_uses" -lt "$temp_uses" ]; then
  echo "  [WARN] More temp operations than cleanup patterns"
  echo "         Review that all temp files are cleaned up"
  warnings=$((warnings + 1))
else
  echo "  [OK] Cleanup patterns appear adequate"
fi

# === Check 5: No test data contains personal info ===
echo ""
echo "=== Check 5: Test Data Sanitization ==="

# Look for personal info in test files (exclude __pycache__ and binary files)
personal_patterns="ben@|bnvoss|veritas|/Users/ben"
personal_found=$(grep -rliE "$personal_patterns" "$TEST_DIR" --include="*.py" --include="*.json" --include="*.yaml" --exclude-dir="__pycache__" 2>/dev/null | head -5)

if [ -n "$personal_found" ]; then
  echo "  [FAIL] Personal info found in test files:"
  for f in $personal_found; do
    echo "    $f"
    grep -hiE "$personal_patterns" "$f" 2>/dev/null | head -1 | sed 's/^/      /'
  done
  failures=$((failures + 1))
else
  echo "  [OK] No personal info in test files"
fi

# === Check 6: Fixtures don't use real database ===
echo ""
echo "=== Check 6: Database Isolation ==="

# Check if tests create their own DB or use fixtures
db_patterns="coordination\.db|sqlite3\.connect|:memory:"
db_uses=$(grep -rcE "$db_patterns" "$TEST_DIR" --include="*.py" 2>/dev/null | awk -F: '{sum+=$2} END {print sum+0}')

memory_db=$(grep -rcE ":memory:" "$TEST_DIR" --include="*.py" 2>/dev/null | awk -F: '{sum+=$2} END {print sum+0}')

echo "  Database operations: $db_uses"
echo "  In-memory databases: $memory_db"

if [ "$db_uses" -gt 0 ] && [ "$memory_db" -eq 0 ]; then
  # Check if using tmp_path for DB
  tmp_db=$(grep -rcE "tmp_path.*\.db|tmpdir.*\.db" "$TEST_DIR" --include="*.py" 2>/dev/null | awk -F: '{sum+=$2} END {print sum+0}')
  if [ "$tmp_db" -eq 0 ]; then
    echo "  [WARN] Database tests may not be using temp paths"
    warnings=$((warnings + 1))
  else
    echo "  [OK] Tests appear to use temp paths for databases"
  fi
else
  echo "  [OK] Database isolation appears adequate"
fi

# === Summary ===
echo ""
echo "==========================================="
echo "Summary:"
echo "  Failures: $failures"
echo "  Warnings: $warnings"
echo ""

if [ $failures -gt 0 ]; then
  echo "FAIL: Test isolation issues detected"
  echo ""
  echo "Tests must not access user's ~/.motus or contain personal info."
  exit 1
fi

if [ $warnings -gt 3 ]; then
  echo "WARN: Multiple test isolation concerns"
  echo "  Review test fixtures before release"
fi

echo "PASS: Test isolation verification complete"
exit 0
