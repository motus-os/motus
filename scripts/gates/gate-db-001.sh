#!/bin/bash
# GATE-DB-001: Schema Version Check
# Reference: .ai/RELEASE-STANDARD.md
# Purpose: Ensure database schema matches code expectations
# Security: No user input, safe for CI
set -e

echo "GATE-DB-001: Schema Version Check"
echo "=================================="

# Verify required commands
for cmd in sqlite3 grep; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "FAIL: Required command '$cmd' not found"
    exit 1
  fi
done

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

SCHEMA_FILE="$REPO_ROOT/src/motus/core/schema.py"
DB_PATH="${HOME:?HOME must be set}/.motus/coordination.db"

# Check if schema file exists
if [ ! -f "$SCHEMA_FILE" ]; then
  echo "WARN: Cannot find schema.py at $SCHEMA_FILE"
  echo "  Skipping version check"
  exit 0
fi

# Get expected version from code
expected=$(grep -E "^SCHEMA_VERSION\s*=" "$SCHEMA_FILE" 2>/dev/null | grep -oE '[0-9]+' | head -1)
if [ -z "$expected" ]; then
  echo "WARN: Cannot determine expected schema version"
  exit 0
fi
echo "Expected schema version: $expected"

# Check if database exists
if [ ! -f "$DB_PATH" ]; then
  echo "WARN: Database not found at $DB_PATH"
  echo "  Run 'motus doctor --fix' to initialize"
  exit 0
fi

# Get actual version from database
actual=$(sqlite3 "$DB_PATH" "SELECT value FROM schema_meta WHERE key='version'" 2>/dev/null || echo "")
if [ -z "$actual" ]; then
  # Try alternative schema query
  actual=$(sqlite3 "$DB_PATH" "PRAGMA user_version" 2>/dev/null || echo "0")
fi
echo "Actual schema version: $actual"

if [ "$actual" != "$expected" ]; then
  echo ""
  echo "FAIL: Schema version mismatch"
  echo "  Expected: $expected"
  echo "  Actual:   $actual"
  echo ""
  echo "Fix: motus doctor --fix"
  exit 1
fi

echo ""
echo "PASS: Schema version $actual matches expected"
exit 0
