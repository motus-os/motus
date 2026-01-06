#!/bin/bash
# GATE-PKG-002: Wheel Content Audit
# Reference: .ai/RELEASE-STANDARD.md
# Purpose: Verify wheel contains ONLY expected files, no dev artifacts
# Security: Prevents test files, secrets, and dev data from shipping
set -e

echo "GATE-PKG-002: Wheel Content Audit"
echo "=================================="

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="${REPO_ROOT:-${MOTUS_REPO_ROOT:-$(cd "$SCRIPT_DIR/../.." && pwd)}}"

# Verify required commands
for cmd in python3 unzip; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "FAIL: Required command '$cmd' not found"
    exit 1
  fi
done

# Find or build wheel
echo ""
echo "=== Locating Wheel ==="

wheel_path=""
DIST_DIR="$REPO_ROOT/dist"
if [ -d "$REPO_ROOT/packages/cli/dist" ]; then
  DIST_DIR="$REPO_ROOT/packages/cli/dist"
fi

if [ -d "$DIST_DIR" ]; then
  wheel_path=$(find "$DIST_DIR" -name "*.whl" -type f | sort -V | tail -1)
fi

if [ -z "$wheel_path" ]; then
  echo "No wheel found in dist/, building..."
  cd "$REPO_ROOT/packages/cli"
  python3 -m build --wheel -q 2>/dev/null || {
    echo "FAIL: Cannot build wheel"
    echo "  Install build: pip install build"
    exit 1
  }
  wheel_path=$(find "$DIST_DIR" -name "*.whl" -type f | sort -V | tail -1)
fi

if [ -z "$wheel_path" ] || [ ! -f "$wheel_path" ]; then
  echo "FAIL: No wheel found"
  exit 1
fi

echo "Wheel: $wheel_path"
wheel_size=$(du -h "$wheel_path" | cut -f1)
wheel_size_kb=$(du -k "$wheel_path" | cut -f1)
echo "Size: $wheel_size"

# Size budget check
MAX_SIZE_KB=5120  # 5MB
if [ "$wheel_size_kb" -gt "$MAX_SIZE_KB" ]; then
  echo ""
  echo "FAIL: Wheel size ${wheel_size} exceeds budget (${MAX_SIZE_KB}KB)"
  echo "  This may indicate accidentally included files"
  exit 1
fi
echo "  [OK] Size within budget"

# Extract wheel to temp dir
tmpdir=$(mktemp -d)
trap "rm -rf $tmpdir" EXIT

echo ""
echo "=== Extracting Wheel ==="
unzip -q "$wheel_path" -d "$tmpdir"

# List all files
echo ""
echo "=== File Inventory ==="
file_count=$(find "$tmpdir" -type f | wc -l | tr -d ' ')
echo "Total files: $file_count"

# Check for blocklisted patterns
echo ""
echo "=== Blocklist Check ==="
blocklist_failed=0

# Files that should NEVER be in a wheel
blocklist_patterns="
*.pyc
__pycache__
.git
.gitignore
.env
*.log
*.db
*.sqlite
*.pickle
*credentials*
*secret*
*api_key*
*token*
test_*.py
*_test.py
conftest.py
pytest.ini
tox.ini
.coverage
htmlcov
.pytest_cache
.mypy_cache
.ruff_cache
"

allowlist_patterns=(
  "motus/safety/test_harness.py"
)

for pattern in $blocklist_patterns; do
  found=$(find "$tmpdir" -name "$pattern" 2>/dev/null | head -5)
  if [ -n "$found" ]; then
    for allow in "${allowlist_patterns[@]}"; do
      found=$(echo "$found" | grep -v "$allow" || true)
    done
  fi
  if [ -n "$found" ]; then
    echo "  [BLOCK] Found '$pattern':"
    echo "$found" | sed 's/^/    /'
    blocklist_failed=1
  fi
done

if [ $blocklist_failed -eq 0 ]; then
  echo "  [OK] No blocklisted files found"
fi

# Check for hardcoded paths in Python files
echo ""
echo "=== Hardcoded Path Scan ==="
path_failed=0

# Patterns that indicate dev environment leakage
path_patterns="/Users/ben|/home/ben|/Users/\w+/|bnvoss|veritas\.associates"

leaked_files=$(grep -rliE "$path_patterns" "$tmpdir" --include="*.py" 2>/dev/null | head -10)
if [ -n "$leaked_files" ]; then
  echo "  [LEAK] Found hardcoded paths in:"
  for f in $leaked_files; do
    echo "    $f"
    grep -hiE "$path_patterns" "$f" 2>/dev/null | head -2 | sed 's/^/      /'
  done
  path_failed=1
else
  echo "  [OK] No hardcoded dev paths found"
fi

# Check for localhost URLs with specific ports (dev servers)
localhost_leaks=$(grep -rliE "localhost:[0-9]{4}|127\.0\.0\.1:[0-9]{4}" "$tmpdir" --include="*.py" 2>/dev/null | head -5)
if [ -n "$localhost_leaks" ]; then
  echo "  [WARN] Found localhost URLs with ports:"
  echo "$localhost_leaks" | sed 's/^/    /'
  echo "  (May be intentional for local servers)"
fi

# Check for email addresses (except official)
echo ""
echo "=== Email Address Scan ==="
email_pattern="[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
# Allow: noreply@anthropic.com, support@motusos.ai, etc.
allowed_emails="noreply@anthropic.com|support@motusos.ai|hello@motusos.ai"

email_leaks=$(grep -rohiE "$email_pattern" "$tmpdir" --include="*.py" 2>/dev/null | grep -viE "$allowed_emails" | sort -u | head -5)
if [ -n "$email_leaks" ]; then
  echo "  [WARN] Found email addresses:"
  echo "$email_leaks" | sed 's/^/    /'
  echo "  (Review if these should be in the package)"
else
  echo "  [OK] No unexpected email addresses"
fi

# Verify expected structure
echo ""
echo "=== Structure Verification ==="
# Should have motusos-*.dist-info and motus/
if [ -d "$tmpdir/motus" ] || [ -d "$tmpdir/motusos" ]; then
  echo "  [OK] Package directory exists"
else
  echo "  [WARN] Expected motus/ or motusos/ directory"
fi

if find "$tmpdir" -name "*.dist-info" -type d | grep -q .; then
  echo "  [OK] dist-info present"
else
  echo "  [WARN] No dist-info found"
fi

# Final verdict
echo ""
echo "=================================="
if [ $blocklist_failed -eq 1 ] || [ $path_failed -eq 1 ]; then
  echo "FAIL: Wheel contains prohibited content"
  echo ""
  echo "The wheel includes files or content that should not ship."
  echo "Check pyproject.toml [tool.hatch.build] or MANIFEST.in"
  exit 1
fi

echo "PASS: Wheel content audit complete"
echo "  Files: $file_count"
echo "  Size: $wheel_size"
echo "  Blocklist: Clear"
echo "  Paths: Clean"
exit 0
