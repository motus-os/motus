#!/bin/bash
# GATE-UPGRADE-001: Upgrade Test
# Reference: .ai/RELEASE-STANDARD.md
# Purpose: Verify upgrading from previous version works
# Security: Validates version input, prevents symlink attacks
set -e

echo "GATE-UPGRADE-001: Upgrade Test"
echo "==============================="

# Configuration
PREV_VERSION="${1:-0.1.0}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="${REPO_ROOT:-${MOTUS_REPO_ROOT:-$(cd "$SCRIPT_DIR/../.." && pwd)}}"

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

# Security: Validate version format (semver only)
if ! [[ "$PREV_VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+(-[a-zA-Z0-9.]+)?$ ]]; then
  echo "FAIL: Invalid version format: $PREV_VERSION"
  echo "  Expected: X.Y.Z or X.Y.Z-suffix"
  exit 1
fi

echo "Previous version: $PREV_VERSION"
echo "Upgrade source: $REPO_ROOT"

# Resolve install root (monorepo vs package)
install_root="$REPO_ROOT"
if [ ! -f "$install_root/pyproject.toml" ] && [ -f "$REPO_ROOT/packages/cli/pyproject.toml" ]; then
  install_root="$REPO_ROOT/packages/cli"
fi

# Verify required commands
for cmd in python3 pip sqlite3; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "FAIL: Required command '$cmd' not found"
    exit 1
  fi
done

# Create temporary directory with secure permissions
umask 077
tmpdir=$(mktemp -d)
echo "Test directory: $tmpdir"

# Security: Verify ownership before cleanup (prevent symlink attacks)
cleanup() {
  if [ -d "$tmpdir" ]; then
    # Cross-platform ownership check
    local owner
    if [[ "$OSTYPE" == "darwin"* ]]; then
      owner=$(stat -f%u "$tmpdir" 2>/dev/null)
    else
      owner=$(stat -c%u "$tmpdir" 2>/dev/null)
    fi
    if [ "$owner" = "$(id -u)" ]; then
      rm -rf "$tmpdir"
    else
      echo "WARN: Skipping cleanup - temp directory ownership mismatch"
    fi
  fi
}
trap cleanup EXIT INT TERM

# Create virtual environment
echo ""
echo "Creating virtual environment..."
python3 -m venv "$tmpdir/venv"

# Use portable activation
. "$tmpdir/venv/bin/activate"

# Isolate DB for the upgrade test
export MOTUS_DATABASE__PATH="$tmpdir/coordination.db"

# Install previous version from PyPI (with timeout)
echo ""
echo "Installing previous version ($PREV_VERSION) from PyPI..."
echo "  NOTE: PyPI packages are verified by pip but not pinned by hash"

if ! timeout_cmd 120 pip install "motusos==$PREV_VERSION" -q 2>/dev/null; then
  echo "WARN: Cannot install motusos==$PREV_VERSION from PyPI"
  echo "  This may be expected for unreleased versions"
  echo "  Skipping upgrade test"
  deactivate
  exit 0
fi

# Verify old version installed
old_version=$(motus --version 2>&1 | head -1 || echo "unknown")
echo "Installed version: $old_version"

# Create some state with old version
echo ""
echo "Creating state with old version..."
motus list >/dev/null 2>&1 || true
motus doctor >/dev/null 2>&1 || true

# Get DB state before upgrade (cross-platform stat)
db_path="$HOME/.motus/coordination.db"
get_file_size() {
  local file="$1"
  if [[ "$OSTYPE" == "darwin"* ]]; then
    stat -f%z "$file" 2>/dev/null || echo "0"
  else
    stat -c%s "$file" 2>/dev/null || echo "0"
  fi
}

if [ -f "$db_path" ]; then
  old_db_size=$(get_file_size "$db_path")
  echo "Database size before: $old_db_size bytes"
fi

# Seed a user-created row to verify non-destructive upgrades.
# Use a low-friction table to avoid policy triggers.
user_item_id="USER-UPGRADE-$(date +%s)"
if [ -f "$db_path" ]; then
  if sqlite3 "$db_path" "SELECT 1 FROM sqlite_master WHERE type='table' AND name='health_check_results';" | grep -q 1; then
    sqlite3 "$db_path" "INSERT INTO health_check_results (check_name, status, message) VALUES ('upgrade_gate', 'pass', '$user_item_id');" || true
  fi
fi

# Upgrade to new version (with timeout)
echo ""
echo "Upgrading to new version..."
timeout_cmd 300 pip install -e "$install_root[dev,web]" -q

# Verify new version
new_version=$(motus --version 2>&1 | head -1)
echo "New version: $new_version"

if [ "$old_version" = "$new_version" ]; then
  echo "WARN: Version unchanged after upgrade"
fi

# Trigger migrations by running a core command, then run doctor
echo ""
echo "Running a command to apply migrations..."
motus list >/dev/null 2>&1 || true

echo ""
echo "Running post-upgrade doctor..."
if motus doctor 2>&1; then
  echo "Doctor: OK"
else
  echo "Doctor reported issues"
fi

# Verify commands still work - MUST pass
echo ""
echo "Verifying commands after upgrade..."
cmd_failed=0
for cmd in list show feed; do
  if motus "$cmd" --help >/dev/null 2>&1; then
    echo "  $cmd: OK"
  else
    echo "  $cmd: FAIL"
    cmd_failed=1
  fi
done

if [ $cmd_failed -eq 1 ]; then
  echo ""
  echo "FAIL: One or more commands broken after upgrade"
  deactivate
  exit 1
fi

# Check DB integrity after upgrade
if [ -f "$db_path" ]; then
  new_db_size=$(get_file_size "$db_path")
  echo ""
  echo "Database size after: $new_db_size bytes"

  # Run integrity check (case-insensitive)
  integrity_result=$(sqlite3 "$db_path" "PRAGMA integrity_check" 2>/dev/null || echo "error")
  if echo "$integrity_result" | grep -qi "^ok$"; then
    echo "Database integrity: OK"
  else
    echo "FAIL: Database integrity check failed"
    echo "  Result: $integrity_result"
    deactivate
    exit 1
  fi

  # Verify user-created row survived upgrade
  if [ -n "$user_item_id" ]; then
    survived=$(sqlite3 "$db_path" "SELECT COUNT(*) FROM health_check_results WHERE message = '$user_item_id';" 2>/dev/null || echo "0")
    if [ "$survived" != "1" ]; then
      echo "FAIL: User data did not survive upgrade (missing $user_item_id)"
      deactivate
      exit 1
    else
      echo "Upgrade data preservation: OK ($user_item_id)"
    fi
  fi
fi

deactivate

echo ""
echo "PASS: Upgrade from $PREV_VERSION successful"
echo "  Old: $old_version"
echo "  New: $new_version"
exit 0
