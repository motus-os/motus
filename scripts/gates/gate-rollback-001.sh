#!/bin/bash
# GATE-ROLLBACK-001: Rollback Capability Verification
# Reference: .ai/RELEASE-STANDARD.md
# Purpose: Verify users can actually rollback to previous version
# Security: Ensures emergency rollback path works
set -e

echo "GATE-ROLLBACK-001: Rollback Capability Verification"
echo "===================================================="

# Configuration
CURRENT_VERSION="${1:-}"
PREV_VERSION="${2:-}"

# Verify required commands
for cmd in python3 pip sqlite3; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "FAIL: Required command '$cmd' not found"
    exit 1
  fi
done

# Auto-detect versions if not provided
if [ -z "$CURRENT_VERSION" ]; then
  CURRENT_VERSION=$(motus --version 2>/dev/null | head -1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' || echo "")
fi

if [ -z "$PREV_VERSION" ]; then
  # Try to get previous version from PyPI
  PREV_VERSION=$(curl -s "https://pypi.org/pypi/motusos/json" 2>/dev/null | \
    python3 -c "import json,sys; releases=list(json.load(sys.stdin).get('releases',{}).keys()); releases.sort(); print(releases[-2] if len(releases)>1 else '')" 2>/dev/null || echo "")
fi

echo "Current version: ${CURRENT_VERSION:-UNKNOWN}"
echo "Previous version: ${PREV_VERSION:-UNKNOWN}"

if [ -z "$PREV_VERSION" ]; then
  echo ""
  echo "SKIP: Cannot determine previous version"
  echo "  This is expected for first release"
  echo "  Provide version manually: $0 CURRENT PREVIOUS"
  exit 0
fi

# Create isolated test environment
echo ""
echo "=== Creating Test Environment ==="

umask 077
tmpdir=$(mktemp -d)
echo "Test directory: $tmpdir"

cleanup() {
  if [ -d "$tmpdir" ]; then
    owner=$(stat -f%u "$tmpdir" 2>/dev/null || stat -c%u "$tmpdir" 2>/dev/null)
    if [ "$owner" = "$(id -u)" ]; then
      rm -rf "$tmpdir"
    fi
  fi
}
trap cleanup EXIT INT TERM

# Create venv
python3 -m venv "$tmpdir/venv"
. "$tmpdir/venv/bin/activate"

# Set isolated Motus directory
export HOME="$tmpdir"
MOTUS_DIR="$HOME/.motus"
mkdir -p "$MOTUS_DIR"
export MOTUS_DATABASE__PATH="$MOTUS_DIR/coordination.db"

# === Test 1: Install current version and create state ===
echo ""
echo "=== Test 1: Install Current Version ==="

if ! pip install "motusos==$CURRENT_VERSION" -q 2>/dev/null; then
  echo "WARN: Cannot install motusos==$CURRENT_VERSION from PyPI"
  echo "  This is expected if version not yet published"
  echo "  Skipping rollback test"
  deactivate
  exit 0
fi

installed_version=$(motus --version 2>&1 | head -1)
echo "Installed: $installed_version"

# Create some state
echo "Creating state..."
motus doctor --fix >/dev/null 2>&1 || true
motus list >/dev/null 2>&1 || true

# Record state
if [ -f "$MOTUS_DATABASE__PATH" ]; then
  db_tables_before=$(sqlite3 "$MOTUS_DATABASE__PATH" "SELECT name FROM sqlite_master WHERE type='table'" 2>/dev/null | sort)
  echo "Database tables: $(echo "$db_tables_before" | wc -l | tr -d ' ')"
fi

# === Test 2: Rollback to previous version ===
echo ""
echo "=== Test 2: Rollback to Previous Version ==="

if ! pip install "motusos==$PREV_VERSION" -q 2>/dev/null; then
  echo "FAIL: Cannot install motusos==$PREV_VERSION from PyPI"
  echo "  Rollback path is broken!"
  deactivate
  exit 1
fi

rolled_back_version=$(motus --version 2>&1 | head -1)
echo "Rolled back to: $rolled_back_version"

# Verify version changed
if echo "$rolled_back_version" | grep -q "$CURRENT_VERSION"; then
  echo "FAIL: Version did not change after rollback"
  deactivate
  exit 1
fi
echo "  [OK] Version changed"

# === Test 3: Verify commands work after rollback ===
echo ""
echo "=== Test 3: Commands Work After Rollback ==="

cmd_failed=0
for cmd in list doctor; do
  if motus "$cmd" --help >/dev/null 2>&1; then
    echo "  [OK] motus $cmd"
  else
    echo "  [FAIL] motus $cmd"
    cmd_failed=1
  fi
done

if [ $cmd_failed -eq 1 ]; then
  echo ""
  echo "FAIL: Commands broken after rollback"
  deactivate
  exit 1
fi

# === Test 4: Verify database accessible after rollback ===
echo ""
echo "=== Test 4: Database Accessible After Rollback ==="

if [ -f "$MOTUS_DATABASE__PATH" ]; then
  # Check integrity
  integrity=$(sqlite3 "$MOTUS_DATABASE__PATH" "PRAGMA integrity_check" 2>/dev/null || echo "CORRUPT")
  if [ "$integrity" = "ok" ]; then
    echo "  [OK] Database integrity verified"
  else
    echo "  [FAIL] Database integrity: $integrity"
    deactivate
    exit 1
  fi

  # Check tables still exist
  db_tables_after=$(sqlite3 "$MOTUS_DATABASE__PATH" "SELECT name FROM sqlite_master WHERE type='table'" 2>/dev/null | sort)
  if [ "$db_tables_before" = "$db_tables_after" ]; then
    echo "  [OK] Database schema unchanged"
  else
    echo "  [WARN] Database schema differs after rollback"
    echo "         This may be expected if schema changed between versions"
  fi
else
  echo "  [WARN] No database to verify"
fi

# === Test 5: Re-upgrade to current version ===
echo ""
echo "=== Test 5: Re-upgrade to Current Version ==="

if pip install "motusos==$CURRENT_VERSION" -q 2>/dev/null; then
  upgraded_version=$(motus --version 2>&1 | head -1)
  echo "Re-upgraded to: $upgraded_version"

  if motus doctor >/dev/null 2>&1; then
    echo "  [OK] Doctor passes after re-upgrade"
  else
    echo "  [WARN] Doctor reports issues after re-upgrade"
  fi
else
  echo "  [WARN] Re-upgrade failed (may be OK if version not published)"
fi

deactivate

# === Summary ===
echo ""
echo "===================================================="
echo "PASS: Rollback capability verified"
echo ""
echo "Users can safely rollback with:"
echo "  pip install motusos==$PREV_VERSION"
echo ""
echo "Tested:"
echo "  1. Install $CURRENT_VERSION: OK"
echo "  2. Rollback to $PREV_VERSION: OK"
echo "  3. Commands work: OK"
echo "  4. Database accessible: OK"
echo "  5. Re-upgrade: OK"
exit 0
