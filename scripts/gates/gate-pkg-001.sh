#!/bin/bash
# GATE-PKG-001: Package Integrity Check
# Reference: .ai/RELEASE-STANDARD.md
# Purpose: Prevent package conflicts causing silent failures
# Security: No user input, safe for CI
set -e

echo "GATE-PKG-001: Package Integrity Check"
echo "======================================"

# Verify required commands
for cmd in pip3 python3; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "FAIL: Required command '$cmd' not found"
    exit 1
  fi
done

# Count motus packages
pkg_list=$(pip3 list 2>/dev/null | grep -E "^motus" || true)
pkg_count=$(echo "$pkg_list" | grep -c "^motus" || echo "0")

echo "Found $pkg_count motus package(s):"
echo "$pkg_list"

# Expected: motusos (required), motus-loom (optional)
# NOT expected: motus, motus-command (old packages)
if echo "$pkg_list" | grep -qE "^motus[[:space:]]|^motus-command"; then
  echo ""
  echo "FAIL: Found conflicting package(s)"
  echo "  These packages shadow the canonical motusos package:"
  echo "$pkg_list" | grep -E "^motus[[:space:]]|^motus-command"
  echo ""
  echo "FIX: pip3 uninstall motus motus-command -y"
  exit 1
fi

# Verify import path
import_path=$(python3 -c "import motus; print(motus.__file__)" 2>/dev/null || echo "IMPORT_FAILED")

if [ "$import_path" = "IMPORT_FAILED" ]; then
  echo ""
  echo "FAIL: Cannot import motus"
  echo "FIX: pip3 install -e .[dev,web]  (from repo root)"
  exit 1
fi

echo ""
echo "Import path: $import_path"

# Check for wrong repo in path
if echo "$import_path" | grep -q "motus-command"; then
  echo ""
  echo "FAIL: motus imports from wrong repository"
  echo "  Expected: .../motus/packages/cli/src/motus/__init__.py"
  echo "  Actual:   $import_path"
  echo ""
  echo "FIX: pip3 uninstall motus motus-command -y"
  exit 1
fi

echo ""
echo "PASS: Package integrity verified"
echo "  - No conflicting packages"
echo "  - Import path is canonical"
