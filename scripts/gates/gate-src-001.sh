#!/bin/bash
# GATE-SRC-001: Source Code Sanitization
# Reference: .ai/RELEASE-STANDARD.md
# Purpose: Verify source code contains no dev artifacts, paths, or personal info
# Security: Prevents internal details from shipping to production
set -e

echo "GATE-SRC-001: Source Code Sanitization"
echo "======================================="

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="${REPO_ROOT:-${MOTUS_REPO_ROOT:-$(cd "$SCRIPT_DIR/../.." && pwd)}}"

# Source directory to scan
SRC_DIR="${1:-$REPO_ROOT/src}"

if [ ! -d "$SRC_DIR" ]; then
  echo "WARN: Source directory not found: $SRC_DIR"
  echo "  Trying alternative locations..."
  for alt in "$REPO_ROOT/src" "$REPO_ROOT/packages/cli/src" "$REPO_ROOT/motus"; do
    if [ -d "$alt" ]; then
      SRC_DIR="$alt"
      break
    fi
  done
fi

if [ ! -d "$SRC_DIR" ]; then
  echo "SKIP: No source directory found to scan"
  exit 0
fi

echo "Scanning: $SRC_DIR"
echo ""

failures=0
warnings=0

# === BLOCKLIST: Must not appear in source ===
echo "=== Blocklist Scan (FAIL if found) ==="

blocklist_patterns=(
  "/Users/ben"
  "/home/ben"
  "bnvoss"
  "ben@.*\.com"
  "veritas\.associates"
  "KnowledgeVault"
  "motus-command"  # internal repo name (legacy)
  "motus-internal"  # internal repo name
  "192\.168\.[0-9]+\.[0-9]+"  # internal IPs
  "62\.72\.7\.98"  # specific VPS
)

# Allowlist: legitimate references that may mention motus-internal / motus-command
allowlist_paths=(
  "src/motus/hardening/package_conflicts.py"
  "src/motus/commands/doctor_cmd.py"
  "src/motus/ui/web/app.py"
  "src/motus/release/evidence_gate.py"
)

for pattern in "${blocklist_patterns[@]}"; do
  matches=$(grep -rniE "$pattern" "$SRC_DIR" --include="*.py" 2>/dev/null | head -20)
  if [ -n "$matches" ]; then
    for allow in "${allowlist_paths[@]}"; do
      matches=$(echo "$matches" | grep -v "$allow" || true)
    done
  fi
  if [ -n "$matches" ]; then
    echo "  [BLOCK] Pattern '$pattern' found:"
    echo "$matches" | sed 's/^/    /'
    failures=$((failures + 1))
  fi
done

if [ $failures -eq 0 ]; then
  echo "  [OK] No blocklisted patterns found"
fi

# === WARN: Should review if found ===
echo ""
echo "=== Warning Patterns (Review if found) ==="

warn_patterns=(
  "TODO.*ben"
  "FIXME.*ben"
  "HACK"
  "XXX"
  "localhost:[0-9]{4}"
  "127\.0\.0\.1:[0-9]{4}"
  "password\s*=\s*[\"']"
  "secret\s*=\s*[\"']"
  "api_key\s*=\s*[\"']"
)

for pattern in "${warn_patterns[@]}"; do
  matches=$(grep -rniE "$pattern" "$SRC_DIR" --include="*.py" 2>/dev/null | head -3)
  if [ -n "$matches" ]; then
    echo "  [WARN] Pattern '$pattern' found:"
    echo "$matches" | sed 's/^/    /'
    warnings=$((warnings + 1))
  fi
done

if [ $warnings -eq 0 ]; then
  echo "  [OK] No warning patterns found"
fi

# === Check for hardcoded credentials (even fake ones in comments) ===
echo ""
echo "=== Credential Pattern Scan ==="

# Patterns that look like credentials
cred_patterns=(
  "sk-[a-zA-Z0-9]{20,}"  # OpenAI-style keys
  "ghp_[a-zA-Z0-9]{36}"  # GitHub PAT
  "github_pat_[a-zA-Z0-9]+"
  "AKIA[A-Z0-9]{16}"  # AWS access key
  "eyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+"  # JWT
)

for pattern in "${cred_patterns[@]}"; do
  matches=$(grep -rnoE "$pattern" "$SRC_DIR" --include="*.py" 2>/dev/null | head -3)
  if [ -n "$matches" ]; then
    echo "  [CRED] Possible credential pattern found:"
    echo "$matches" | sed 's/^/    /'
    failures=$((failures + 1))
  fi
done

# === Check __init__.py doesn't expose internal paths ===
echo ""
echo "=== Module Path Check ==="

init_files=$(find "$SRC_DIR" -name "__init__.py" 2>/dev/null)
for init in $init_files; do
  if grep -qE "__file__|__path__" "$init" 2>/dev/null; then
    # This is OK if used for package introspection
    # But check if it logs or prints paths
    if grep -qE "print.*__file__|log.*__file__" "$init" 2>/dev/null; then
      echo "  [WARN] $init may expose file paths in output"
      warnings=$((warnings + 1))
    fi
  fi
done
echo "  [OK] Module path check complete"

# === Check for print statements (should use logging) ===
echo ""
echo "=== Print Statement Check ==="
print_count=$(grep -rcE "^\s*print\(" "$SRC_DIR" --include="*.py" 2>/dev/null | awk -F: '{sum+=$2} END {print sum+0}')
if [ "$print_count" -gt 10 ]; then
  echo "  [WARN] Found $print_count print() statements"
  echo "         Consider using logging for production code"
  warnings=$((warnings + 1))
else
  echo "  [OK] Print statement count acceptable ($print_count)"
fi

# === Check for assert statements (can be optimized away) ===
echo ""
echo "=== Assert Statement Check ==="
assert_count=$(grep -rcE "^\s*assert\s" "$SRC_DIR" --include="*.py" 2>/dev/null | awk -F: '{sum+=$2} END {print sum+0}')
if [ "$assert_count" -gt 50 ]; then
  echo "  [WARN] Found $assert_count assert statements"
  echo "         Asserts are stripped with python -O"
  warnings=$((warnings + 1))
else
  echo "  [OK] Assert statement count acceptable ($assert_count)"
fi

# === Summary ===
echo ""
echo "======================================="
echo "Summary:"
echo "  Failures: $failures"
echo "  Warnings: $warnings"
echo ""

if [ $failures -gt 0 ]; then
  echo "FAIL: Source code contains prohibited content"
  echo ""
  echo "Fix the blocklisted patterns before release."
  exit 1
fi

if [ $warnings -gt 5 ]; then
  echo "WARN: Multiple warning patterns found"
  echo "  Review before release, but not blocking"
fi

echo "PASS: Source code sanitization complete"
exit 0
