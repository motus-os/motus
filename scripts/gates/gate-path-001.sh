#!/usr/bin/env bash
# GATE-PATH-001: Legacy path references
# Purpose: Block new .mc/ references outside approved legacy shims
set -euo pipefail

echo "GATE-PATH-001: Legacy path reference guard"
echo "==========================================="

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="${REPO_ROOT:-${MOTUS_REPO_ROOT:-$(cd "$SCRIPT_DIR/../.." && pwd)}}"

SRC_DIR="$REPO_ROOT/packages/cli/src/motus"

if [ ! -d "$SRC_DIR" ]; then
  echo "SKIP: Source directory not found: $SRC_DIR"
  exit 0
fi

if command -v rg >/dev/null 2>&1; then
  matches=$(rg -n "\\.mc/" "$SRC_DIR" --type py --glob '!**/migration/path_migration.py' || true)
else
  matches=$(grep -RIn "\\.mc/" "$SRC_DIR" --include="*.py" | grep -v "migration/path_migration.py" || true)
fi
if [ -z "$matches" ]; then
  echo "PASS: No .mc/ references found"
  exit 0
fi

filtered=$(echo "$matches" | grep -v "LEGACY" || true)
if [ -n "$filtered" ]; then
  echo "FAIL: New .mc/ references found (must be removed or marked LEGACY):"
  echo "$filtered"
  exit 1
fi

echo "PASS: .mc/ references are legacy-only"
exit 0
