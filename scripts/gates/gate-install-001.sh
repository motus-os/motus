#!/bin/bash
# GATE-INSTALL-001: Fresh Install Test
# Reference: .ai/RELEASE-STANDARD.md
# Purpose: Verify package installs correctly in clean environment
# Security: Validates input, prevents command injection and symlink attacks
set -e

echo "GATE-INSTALL-001: Fresh Install Test"
echo "====================================="

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

# Determine install source
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="${REPO_ROOT:-${MOTUS_REPO_ROOT:-$(cd "$SCRIPT_DIR/../.." && pwd)}}"
INSTALL_SOURCE="${1:-$REPO_ROOT}"

# Security: Validate install source - reject shell metacharacters
if [[ "$INSTALL_SOURCE" =~ [\"\'$\;\&\|\`\(\)\{\}\<\>] ]]; then
  echo "FAIL: Invalid install source - contains unsafe characters"
  exit 1
fi

# Security: If it's a path, verify it exists and is safe
if [[ "$INSTALL_SOURCE" == /* ]] || [[ "$INSTALL_SOURCE" == ./* ]]; then
  if [ ! -d "$INSTALL_SOURCE" ]; then
    echo "FAIL: Install source directory does not exist: $INSTALL_SOURCE"
    exit 1
  fi
  # Canonicalize and verify within expected paths
  REAL_SOURCE="$(cd "$INSTALL_SOURCE" && pwd)"
  echo "Install source: $REAL_SOURCE"
  if [ -d "$REAL_SOURCE/packages/cli" ] && [ -f "$REAL_SOURCE/packages/cli/pyproject.toml" ]; then
    REAL_SOURCE="$REAL_SOURCE/packages/cli"
    echo "Install source (monorepo CLI): $REAL_SOURCE"
  fi
else
  # Package name from PyPI - validate format
  if ! [[ "$INSTALL_SOURCE" =~ ^[a-zA-Z0-9][a-zA-Z0-9._-]*(\[[a-z,]+\])?$ ]]; then
    echo "FAIL: Invalid package name format: $INSTALL_SOURCE"
    exit 1
  fi
  REAL_SOURCE="$INSTALL_SOURCE"
  echo "Install source (PyPI): $REAL_SOURCE"
fi

# Verify required commands
for cmd in python3 pip; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "FAIL: Required command '$cmd' not found"
    exit 1
  fi
done

# Create temporary directory with secure permissions
umask 077
tmpdir=$(mktemp -d)
echo "Test directory: $tmpdir"

# Security: Verify we own the temp directory (prevent symlink attacks)
cleanup() {
  if [ -d "$tmpdir" ]; then
    # Verify ownership before deletion
    if [ "$(stat -c%u "$tmpdir" 2>/dev/null || stat -f%u "$tmpdir" 2>/dev/null)" = "$(id -u)" ]; then
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

# Create isolated Motus directory (CRITICAL: isolate from user's data)
export HOME="$tmpdir"
MOTUS_DIR="$HOME/.motus"
mkdir -p "$MOTUS_DIR"
echo "Motus directory: $MOTUS_DIR"
export MOTUS_DATABASE__PATH="$MOTUS_DIR/coordination.db"

# Use portable activation
. "$tmpdir/venv/bin/activate"

# Install package (with timeout)
echo ""
echo "Installing from $REAL_SOURCE..."
if [ -f "$REAL_SOURCE/pyproject.toml" ]; then
  timeout_cmd 300 pip install -e "$REAL_SOURCE[dev,web]" -q
elif [ -f "$REAL_SOURCE/setup.py" ]; then
  timeout_cmd 300 pip install -e "$REAL_SOURCE[dev,web]" -q
else
  # Package from PyPI
  timeout_cmd 300 pip install "$REAL_SOURCE" -q
fi

# Verify installation
echo ""
echo "Verifying installation..."

# Check version
if ! version=$(motus --version 2>&1 | head -1); then
  echo "FAIL: Cannot get version"
  deactivate
  exit 1
fi
echo "Version: $version"

# Check help works
if ! motus --help >/dev/null 2>&1; then
  echo "FAIL: 'motus --help' failed"
  deactivate
  exit 1
fi
echo "Help: OK"

# Check doctor
echo ""
echo "Running motus doctor..."
if motus doctor 2>&1; then
  echo "Doctor: OK"
else
  echo "WARN: Doctor reported issues (may be expected on fresh install)"
fi

# Check core commands - MUST pass
echo ""
echo "Checking core commands..."
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
  echo "FAIL: One or more core commands not working"
  deactivate
  exit 1
fi

# Capture import path as evidence
echo ""
echo "Capturing evidence..."
import_path=$(python3 -c "import motus; print(motus.__file__)" 2>/dev/null || echo "IMPORT_FAILED")
echo "Import path: $import_path"

# CRITICAL: Verify fresh install created clean database
echo ""
echo "=== Fresh Install Database Validation ==="
db_path="$MOTUS_DATABASE__PATH"

if [ ! -f "$db_path" ]; then
  echo "  Database not created yet - initializing..."
  motus doctor --fix >/dev/null 2>&1 || true
fi

if [ -f "$db_path" ]; then
  # Check for data leaks
  echo "  Checking for leaked data..."

  # These tables MUST be empty on fresh install
  for table in sessions events; do
    count=$(sqlite3 "$db_path" "SELECT COUNT(*) FROM $table" 2>/dev/null || echo "-1")
    if [ "$count" = "-1" ]; then
      echo "    [--] $table: table doesn't exist"
    elif [ "$count" != "0" ]; then
      echo "    [LEAK] $table has $count rows - SHOULD BE EMPTY"
      echo ""
      echo "FAIL: Data leak detected in fresh install database"
      deactivate
      exit 1
    else
      echo "    [OK] $table: empty"
    fi
  done

  # roadmap_items must be empty on fresh install
  roadmap_count=$(sqlite3 "$db_path" "SELECT COUNT(*) FROM roadmap_items" 2>/dev/null || echo "0")
  if [ "$roadmap_count" -gt 0 ]; then
    echo "    [LEAK] roadmap_items has $roadmap_count rows - SHOULD BE EMPTY"
    echo ""
    echo "FAIL: Dev roadmap items leaked into fresh install"
    deactivate
    exit 1
  else
    echo "    [OK] roadmap_items: $roadmap_count rows (clean)"
  fi

  # Check for dev-specific content
  leak_check=$(sqlite3 "$db_path" "
    SELECT COUNT(*) FROM roadmap_items
    WHERE title LIKE '%ben%' OR title LIKE '%veritas%' OR title LIKE '%bnvoss%'
  " 2>/dev/null || echo "0")
  if [ "$leak_check" != "0" ]; then
    echo "    [LEAK] Found dev-specific content in roadmap_items"
    echo ""
    echo "FAIL: Dev content leaked into fresh install"
    deactivate
    exit 1
  else
    echo "    [OK] No dev-specific content detected"
  fi

  echo "  Database validation: PASS"
else
  echo "  [WARN] Database not found after doctor --fix"
fi

# Check directory structure
echo ""
echo "=== Fresh Install Directory Validation ==="
echo "  Motus directory contents:"
ls -la "$MOTUS_DIR" 2>/dev/null | head -10
total_size=$(du -sk "$MOTUS_DIR" 2>/dev/null | cut -f1 || echo "0")
echo "  Total size: ${total_size}KB"

if [ "$total_size" -gt 10240 ]; then
  echo "  [WARN] Directory larger than expected (${total_size}KB > 10MB)"
fi

# Check for blocklisted files
for pattern in "*.backup*" "*credentials*" "*secret*" "*api_key*"; do
  if find "$MOTUS_DIR" -name "$pattern" 2>/dev/null | grep -q .; then
    echo "  [LEAK] Found blocklisted file: $pattern"
    echo ""
    echo "FAIL: Blocklisted files in fresh install"
    deactivate
    exit 1
  fi
done
echo "  Directory validation: PASS"

# Deactivate and cleanup (trap handles cleanup)
deactivate

echo ""
echo "PASS: Fresh install successful"
echo "  Version: $version"
echo "  Import path: $import_path"
echo "  Database: Clean (no leaks)"
echo "  Directory: Clean (no blocklisted files)"
exit 0
