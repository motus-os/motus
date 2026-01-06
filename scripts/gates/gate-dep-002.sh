#!/bin/bash
# GATE-DEP-002: Dependency License Check
# Reference: .ai/RELEASE-STANDARD.md
# Purpose: Block release if dependencies have incompatible licenses
# Security: Fail-closed - GPL/AGPL contamination = blocked release
set -e

echo "GATE-DEP-002: Dependency License Check"
echo "======================================="

# Verify required commands
if ! command -v pip-licenses >/dev/null 2>&1; then
  echo "FAIL: pip-licenses not installed"
  echo ""
  echo "Install with: pip install pip-licenses"
  exit 1
fi

# Allowed licenses (permissive, enterprise-friendly)
ALLOWED="MIT;Apache Software License;BSD License;BSD-2-Clause;BSD-3-Clause;ISC License;Python Software Foundation License;PSF;Apache-2.0;Apache 2.0;Unlicense;Public Domain;CC0"

# Blocked licenses (copyleft, viral)
BLOCKED="GPL;LGPL;AGPL;GNU General Public License;GNU Lesser General Public License;GNU Affero General Public License"

echo "Checking dependency licenses..."
echo ""

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Get motus's actual dependencies via pip show (works in any environment)
# This avoids flagging unrelated packages in the environment
echo "Extracting motus package dependencies..."
deps=$(python3 -c "
import subprocess
import re
result = subprocess.run(['pip', 'show', 'motusos'], capture_output=True, text=True)
if result.returncode != 0:
    # Try alternative package name
    result = subprocess.run(['pip', 'show', 'motus'], capture_output=True, text=True)
if result.returncode == 0:
    for line in result.stdout.split('\n'):
        if line.startswith('Requires:'):
            deps = line.split(':', 1)[1].strip()
            if deps:
                print(' '.join(d.strip().lower() for d in deps.split(',')))
" 2>/dev/null || echo "")

if [ -n "$deps" ]; then
  echo "Found $(echo "$deps" | wc -w | tr -d ' ') package dependencies"
else
  echo "WARN: Could not extract motus dependencies, checking all packages"
  echo "  (This is expected if motusos is not installed)"
fi

# Get all licenses
all_licenses=$(pip-licenses --format=csv 2>/dev/null || echo "ERROR")

if [ "$all_licenses" = "ERROR" ]; then
  echo "FAIL: Could not retrieve license information"
  exit 1
fi

# Check for blocked licenses
echo ""
echo "Scanning for blocked licenses in project dependencies..."
blocked_found=""
while IFS=, read -r name version license; do
  # Skip header
  [ "$name" = "Name" ] && continue

  # If we have a deps list, only check those packages
  if [ -n "$deps" ]; then
    name_lower=$(echo "$name" | tr '[:upper:]' '[:lower:]')
    if ! echo "$deps" | grep -qw "$name_lower"; then
      continue  # Skip packages not in our dependencies
    fi
  fi

  # Check if license matches any blocked pattern
  for pattern in GPL LGPL AGPL "GNU General" "GNU Lesser" "GNU Affero"; do
    if echo "$license" | grep -qi "$pattern"; then
      # Exception: LGPL allows dynamic linking (acceptable for Python)
      if echo "$license" | grep -qi "LGPL"; then
        echo "  [WARN] $name ($version): $license (LGPL - acceptable for Python)"
      else
        blocked_found="$blocked_found\n  $name ($version): $license"
      fi
    fi
  done
done <<< "$all_licenses"

if [ -n "$blocked_found" ]; then
  echo ""
  echo "FAIL: Blocked licenses found:"
  echo -e "$blocked_found"
  echo ""
  echo "These licenses are incompatible with commercial distribution."
  echo "Either:"
  echo "  1. Remove the dependency"
  echo "  2. Find an alternative with permissive license"
  echo "  3. Get legal approval for exception"
  exit 1
fi

# Summary
echo ""
echo "License summary:"
pip-licenses --summary 2>/dev/null | head -20

echo ""
echo "PASS: No blocked licenses found"
echo ""
echo "NOTE: LGPL dependencies are acceptable for Python (dynamic linking)"
exit 0
