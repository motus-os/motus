#!/bin/bash
# GATE-FRESH-002: Fresh Install Directory Validation
# Reference: .ai/RELEASE-STANDARD.md
# Purpose: Verify fresh install creates correct directory structure with NO dev artifacts
# Security: Prevents config files and dev artifacts from leaking
set -e

echo "GATE-FRESH-002: Fresh Install Directory Validation"
echo "==================================================="

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

# Configuration: isolate Motus directory
umask 077
tmpdir=$(mktemp -d)
export HOME="$tmpdir"
MOTUS_DIR="$HOME/.motus"
export MOTUS_DATABASE__PATH="$MOTUS_DIR/coordination.db"

cleanup() {
  if [ -d "$tmpdir" ]; then
    rm -rf "$tmpdir"
  fi
}
trap cleanup EXIT INT TERM

echo "Motus directory: $MOTUS_DIR"
echo ""

# Ensure fresh install initializes
timeout_cmd 30 motus doctor --fix >/dev/null 2>&1 || true

# Check 1: Directory exists
echo "Check 1: Directory exists"
if [ ! -d "$MOTUS_DIR" ]; then
  echo "FAIL: Motus directory not found at $MOTUS_DIR"
  echo "  Run 'motus doctor --fix' to initialize"
  exit 1
fi
echo "  [OK] Directory exists"

# Check 2: Expected files/directories
echo ""
echo "Check 2: Expected structure"
expected_items="coordination.db"  # Minimum expected
optional_items="config.json bin state tmp traces"

for item in $expected_items; do
  if [ -e "$MOTUS_DIR/$item" ]; then
    echo "  [OK] $item exists (required)"
  else
    echo "  [FAIL] $item missing (required)"
    exit 1
  fi
done

for item in $optional_items; do
  if [ -e "$MOTUS_DIR/$item" ]; then
    echo "  [OK] $item exists (optional)"
  else
    echo "  [--] $item not present (optional)"
  fi
done

# Check 3: NO unexpected files (leak detection)
echo ""
echo "Check 3: Unexpected file detection"
leak_detected=0

# Files that should NOT exist in fresh install
blocklist_patterns="
*.backup*
*.bak
*credentials*
*secret*
*token*
*api_key*
*.pickle
*.log
.env
"

for pattern in $blocklist_patterns; do
  found=$(find "$MOTUS_DIR" -name "$pattern" 2>/dev/null | head -5)
  if [ -n "$found" ]; then
    echo "  [LEAK] Found blocklisted file pattern '$pattern':"
    echo "$found" | sed 's/^/    /'
    leak_detected=1
  fi
done

# Check 4: No dev-specific paths in config
echo ""
echo "Check 4: Config content scan"

if [ -f "$MOTUS_DIR/config.json" ]; then
  # Check for dev paths
  if grep -qiE "/Users/ben|bnvoss|veritas|localhost:4000" "$MOTUS_DIR/config.json" 2>/dev/null; then
    echo "  [LEAK] config.json contains dev-specific paths:"
    grep -iE "/Users/ben|bnvoss|veritas" "$MOTUS_DIR/config.json" | head -3
    leak_detected=1
  else
    echo "  [OK] config.json has no dev-specific paths"
  fi
else
  echo "  [--] No config.json (OK for fresh install)"
fi

# Check 5: Directory permissions
echo ""
echo "Check 5: Directory permissions"
dir_perms=$(stat -f%Lp "$MOTUS_DIR" 2>/dev/null || stat -c%a "$MOTUS_DIR" 2>/dev/null)
if [ "$dir_perms" = "700" ] || [ "$dir_perms" = "755" ]; then
  echo "  [OK] Directory permissions: $dir_perms"
else
  echo "  [WARN] Directory permissions: $dir_perms (expected 700 or 755)"
fi

db_perms=$(stat -f%Lp "$MOTUS_DIR/coordination.db" 2>/dev/null || stat -c%a "$MOTUS_DIR/coordination.db" 2>/dev/null)
if [ "$db_perms" = "600" ] || [ "$db_perms" = "644" ]; then
  echo "  [OK] Database permissions: $db_perms"
else
  echo "  [WARN] Database permissions: $db_perms (expected 600 or 644)"
fi

# Check 6: Total size sanity check
echo ""
echo "Check 6: Size sanity check"
total_size=$(du -sk "$MOTUS_DIR" 2>/dev/null | cut -f1)
echo "  Total directory size: ${total_size}KB"

# Fresh install should be small (< 1MB typically)
if [ "$total_size" -gt 10240 ]; then
  echo "  [WARN] Directory larger than expected (${total_size}KB > 10MB)"
  echo "         This may indicate leftover data"
  # Not a hard fail, but suspicious
fi

# Final verdict
echo ""
echo "==================================================="
if [ $leak_detected -eq 1 ]; then
  echo "FAIL: Dev artifacts detected in fresh install"
  echo ""
  echo "CRITICAL: Dev files have leaked into the directory."
  echo "DO NOT RELEASE until this is fixed."
  exit 1
fi

echo "PASS: Fresh install directory structure is clean"
echo "  - Required files present"
echo "  - No blocklisted files"
echo "  - No dev-specific content"
exit 0
