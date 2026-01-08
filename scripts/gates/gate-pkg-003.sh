#!/bin/bash
# GATE-PKG-003: SDist Content Audit
# Purpose: Verify sdist contains only approved sources and no internal artifacts
# Security: Prevents internal data from shipping in source distributions
set -e

echo "GATE-PKG-003: SDist Content Audit"
echo "================================="

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="${REPO_ROOT:-${MOTUS_REPO_ROOT:-$(cd "$SCRIPT_DIR/../.." && pwd)}}"

# Verify required commands
for cmd in python3 tar; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "FAIL: Required command '$cmd' not found"
    exit 1
  fi
done

# Find or build sdist
echo ""
echo "=== Locating SDist ==="

sdist_path=""
DIST_DIR="$REPO_ROOT/dist"
if [ -d "$REPO_ROOT/packages/cli/dist" ]; then
  DIST_DIR="$REPO_ROOT/packages/cli/dist"
fi

if [ -d "$DIST_DIR" ]; then
  sdist_path=$(find "$DIST_DIR" -name "*.tar.gz" -type f | sort -V | tail -1)
fi

if [ -z "$sdist_path" ]; then
  echo "No sdist found in dist/, building..."
  cd "$REPO_ROOT/packages/cli"
  python3 -m build --sdist || {
    echo "FAIL: Cannot build sdist"
    echo "  Install build: pip install build"
    exit 1
  }
  sdist_path=$(find "$DIST_DIR" -name "*.tar.gz" -type f | sort -V | tail -1)
fi

if [ -z "$sdist_path" ] || [ ! -f "$sdist_path" ]; then
  echo "FAIL: No sdist found"
  exit 1
fi

echo "SDist: $sdist_path"

# Extract sdist to temp dir
tmpdir=$(mktemp -d)
trap "rm -rf $tmpdir" EXIT

echo ""
echo "=== Extracting SDist ==="
tar -xf "$sdist_path" -C "$tmpdir"

root_dir=$(tar -tf "$sdist_path" | head -1 | cut -d/ -f1)
if [ -z "$root_dir" ]; then
  echo "FAIL: Unable to determine sdist root directory"
  exit 1
fi
root_path="$tmpdir/$root_dir"
if [ ! -d "$root_path" ]; then
  echo "FAIL: SDist root directory missing: $root_path"
  exit 1
fi

# Allowlist check for sdist root entries
echo ""
echo "=== Root Allowlist Check ==="
allowlist_failed=0
allowed_root_entries=(
  "src"
  "migrations"
  "README.md"
  "LICENSE"
  "LICENSING.md"
  "NOTICE"
  "TRADEMARKS.md"
  "pyproject.toml"
  "PKG-INFO"
  ".gitignore"
)

for entry in $(find "$root_path" -mindepth 1 -maxdepth 1 -print | sed 's|.*/||'); do
  allowed=0
  for allow in "${allowed_root_entries[@]}"; do
    if [ "$entry" = "$allow" ]; then
      allowed=1
      break
    fi
  done
  if [ $allowed -eq 0 ]; then
    echo "  [BLOCK] Unexpected root entry: $entry"
    allowlist_failed=1
  fi
done

if [ $allowlist_failed -eq 0 ]; then
  echo "  [OK] Root entries match allowlist"
fi

echo ""
echo "=== Internal Artifact Scan ==="
internal_hits=$(find "$root_path" \( -path "*/.ai/*" -o -path "*/.github/*" -o -path "*/scripts/*" -o -path "*/.codex/*" \) -print 2>/dev/null | head -10)
if [ -n "$internal_hits" ]; then
  echo "  [BLOCK] Internal artifacts found:"
  echo "$internal_hits" | sed 's/^/    /'
  allowlist_failed=1
else
  echo "  [OK] No internal artifacts found"
fi

# Check for blocklisted patterns
echo ""
echo "=== Blocklist Check ==="
blocklist_failed=0

blocklist_patterns="
*.pyc
__pycache__
.git
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

for pattern in $blocklist_patterns; do
  found=$(find "$root_path" -name "$pattern" 2>/dev/null | head -5)
  if [ -n "$found" ]; then
    echo "  [BLOCK] Found '$pattern':"
    echo "$found" | sed 's/^/    /'
    blocklist_failed=1
  fi
done

if [ $blocklist_failed -eq 0 ]; then
  echo "  [OK] No blocklisted files found"
fi

echo ""
echo "=================================="
if [ $blocklist_failed -eq 1 ] || [ $allowlist_failed -eq 1 ]; then
  echo "FAIL: SDist contains prohibited content"
  echo ""
  exit 1
fi

echo "PASS: SDist content audit complete"
exit 0
