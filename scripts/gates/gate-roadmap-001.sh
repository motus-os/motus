#!/bin/bash
# GATE-ROADMAP-001: Roadmap Hygiene
# Reference: packages/cli/docs/standards/gates.yaml
# Purpose: Enforce basic roadmap data integrity
# Security: Read-only checks against coordination.db
set -e

echo "GATE-ROADMAP-001: Roadmap Hygiene"
echo "=================================="

# Verify required commands
for cmd in sqlite3; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "FAIL: Required command '$cmd' not found"
    exit 1
  fi
done

DB_PATH="${MOTUS_DATABASE__PATH:-$HOME/.motus/coordination.db}"

echo "Database path: $DB_PATH"

if [ ! -f "$DB_PATH" ]; then
  echo "WARN: Database not found; skipping roadmap hygiene checks."
  exit 0
fi

failures=0

check_count() {
  local label="$1"
  local sql="$2"
  local count
  count=$(sqlite3 "$DB_PATH" "$sql" 2>/dev/null || echo "")
  if [ -z "$count" ]; then
    echo "  [WARN] $label (query failed)"
    return
  fi
  if [ "$count" -gt 0 ]; then
    echo "  [FAIL] $label: $count"
    failures=$((failures + 1))
  else
    echo "  [OK] $label: 0"
  fi
}

warn_count() {
  local label="$1"
  local sql="$2"
  local count
  count=$(sqlite3 "$DB_PATH" "$sql" 2>/dev/null || echo "")
  if [ -z "$count" ]; then
    echo "  [WARN] $label (query failed)"
    return
  fi
  if [ "$count" -gt 0 ]; then
    echo "  [WARN] $label: $count"
  else
    echo "  [OK] $label: 0"
  fi
}

# Basic integrity checks
check_count "Empty roadmap IDs" "SELECT COUNT(*) FROM roadmap_items WHERE deleted_at IS NULL AND (id IS NULL OR TRIM(id)='');"
check_count "Missing phase_key" "SELECT COUNT(*) FROM roadmap_items WHERE deleted_at IS NULL AND (phase_key IS NULL OR TRIM(phase_key)='');"
check_count "Missing title" "SELECT COUNT(*) FROM roadmap_items WHERE deleted_at IS NULL AND (title IS NULL OR TRIM(title)='');"
check_count "In-progress without owner" "SELECT COUNT(*) FROM roadmap_items WHERE deleted_at IS NULL AND status_key='in_progress' AND (owner IS NULL OR TRIM(owner)='');"

# Status sanity check (allow legacy backlog/queue)
check_count "Unknown status_key" "SELECT COUNT(*) FROM roadmap_items WHERE deleted_at IS NULL AND status_key NOT IN ('pending','in_progress','blocked','completed','deferred','backlog','queue');"

# Non-blocking hygiene warnings
warn_count "Completed without completed_at" "SELECT COUNT(*) FROM roadmap_items WHERE deleted_at IS NULL AND status_key='completed' AND (completed_at IS NULL OR TRIM(completed_at)='');"

if [ $failures -gt 0 ]; then
  echo ""
  echo "FAIL: Roadmap hygiene checks failed ($failures)"
  exit 1
fi

echo ""
echo "PASS: Roadmap hygiene checks" 
exit 0
