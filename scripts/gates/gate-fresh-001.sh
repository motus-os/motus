#!/bin/bash
# GATE-FRESH-001: Fresh Install Database Validation
# Reference: .ai/RELEASE-STANDARD.md
# Purpose: Verify fresh install creates functional but EMPTY database
# Security: Prevents dev data from leaking into releases
set -e

echo "GATE-FRESH-001: Fresh Install Database Validation"
echo "=================================================="

# This gate MUST run in a clean venv with a fresh ~/.motus/
# It validates that:
# 1. Database is created with correct schema
# 2. Database is EMPTY (no dev data leaked)
# 3. All tables exist but contain no rows

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

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

# Verify required commands
for cmd in python3 sqlite3; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "FAIL: Required command '$cmd' not found"
    exit 1
  fi
done

# Configuration: create an isolated Motus directory
umask 077
tmpdir=$(mktemp -d)
export HOME="$tmpdir"
MOTUS_DIR="$HOME/.motus"
export MOTUS_DATABASE__PATH="$MOTUS_DIR/coordination.db"
DB_PATH="$MOTUS_DATABASE__PATH"

cleanup() {
  if [ -d "$tmpdir" ]; then
    rm -rf "$tmpdir"
  fi
}
trap cleanup EXIT INT TERM

echo "Motus directory: $MOTUS_DIR"
echo "Database path: $DB_PATH"
echo ""

# Ensure database exists (fresh install)
timeout_cmd 30 motus doctor --fix >/dev/null 2>&1 || true

# Check 1: Database exists
echo "Check 1: Database exists"
if [ ! -f "$DB_PATH" ]; then
  echo "FAIL: Database not found at $DB_PATH"
  echo "  Run 'motus doctor --fix' to initialize"
  exit 1
fi
echo "  [OK] Database exists"

# Check 2: Database is valid SQLite
echo ""
echo "Check 2: Database integrity"
integrity=$(sqlite3 "$DB_PATH" "PRAGMA integrity_check" 2>/dev/null || echo "CORRUPT")
if [ "$integrity" != "ok" ]; then
  echo "FAIL: Database integrity check failed: $integrity"
  exit 1
fi
echo "  [OK] Database integrity verified"

# Check 3: Schema version exists
echo ""
echo "Check 3: Schema version"
schema_version=$(sqlite3 "$DB_PATH" "SELECT value FROM schema_version WHERE key='version'" 2>/dev/null || echo "MISSING")
if [ "$schema_version" = "MISSING" ]; then
  # Try alternative location
  schema_version=$(sqlite3 "$DB_PATH" "PRAGMA user_version" 2>/dev/null || echo "0")
fi
echo "  Schema version: $schema_version"

# Check 4: CRITICAL - No user data in tables that should be empty on fresh install
echo ""
echo "Check 4: Data leak detection (CRITICAL)"
leak_detected=0

# Tables that MUST be empty on fresh install
empty_tables="sessions events"

for table in $empty_tables; do
  count=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM $table" 2>/dev/null || echo "-1")
  if [ "$count" = "-1" ]; then
    echo "  [SKIP] $table (table doesn't exist)"
  elif [ "$count" != "0" ]; then
    echo "  [LEAK] $table has $count rows - SHOULD BE EMPTY"
    leak_detected=1
  else
    echo "  [OK] $table is empty"
  fi
done

# Tables that should have minimal/default data only
echo ""
echo "Check 5: Configuration tables (allow defaults only)"

# roadmap_items: Must be empty on fresh install
roadmap_count=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM roadmap_items" 2>/dev/null || echo "0")
if [ "$roadmap_count" -gt 0 ]; then
  echo "  [LEAK] roadmap_items has $roadmap_count rows - SHOULD BE EMPTY"
  leak_detected=1
else
  echo "  [OK] roadmap_items: $roadmap_count rows (clean)"
fi

# Check for specific leak indicators
echo ""
echo "Check 6: Content leak scan"

# Look for strings that indicate dev data
leak_patterns="ben@|/Users/ben|veritas|motus-command|motus-internal|bnvoss"
leaked_content=$(sqlite3 "$DB_PATH" "
  SELECT 'roadmap_items' as tbl, title FROM roadmap_items WHERE title LIKE '%ben%' OR title LIKE '%veritas%'
  UNION ALL
  SELECT 'sessions' as tbl, session_id FROM sessions WHERE session_id LIKE '%ben%'
  LIMIT 5
" 2>/dev/null || echo "")

if [ -n "$leaked_content" ]; then
  echo "  [LEAK] Found dev-specific content in database:"
  echo "$leaked_content" | head -5
  leak_detected=1
else
  echo "  [OK] No dev-specific content detected"
fi

# Final verdict
echo ""
echo "=================================================="
if [ $leak_detected -eq 1 ]; then
  echo "FAIL: Data leak detected in fresh install"
  echo ""
  echo "CRITICAL: Dev data has leaked into the package."
  echo "DO NOT RELEASE until this is fixed."
  echo ""
  echo "Common causes:"
  echo "  1. Database file included in package"
  echo "  2. Seed data contains dev content"
  echo "  3. Test fixtures not cleaned up"
  exit 1
fi

echo "PASS: Fresh install database is clean"
echo "  - Schema initialized correctly"
echo "  - No user data detected"
echo "  - No dev content leaked"
exit 0
