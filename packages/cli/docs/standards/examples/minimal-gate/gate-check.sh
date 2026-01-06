#!/bin/bash
# gate-check.sh - Simplest possible Motus gate
#
# A gate is a script that:
# - Exits 0 on success (PASS)
# - Exits non-zero on failure (FAIL)
# - Writes diagnostic output to stdout/stderr

set -e  # Exit on error

echo "=== Minimal Gate Check ==="
echo "Run ID: ${MOTUS_RUN_ID:-unknown}"
echo "Repo: ${MOTUS_REPO_DIR:-$(pwd)}"
echo ""

# Example: Check that README exists
if [ -f "README.md" ]; then
    echo "[PASS] README.md exists"
else
    echo "[FAIL] README.md not found"
    exit 1
fi

# Example: Check that no TODO markers in critical files
if grep -r "TODO" src/ 2>/dev/null; then
    echo "[WARN] Found TODO markers (non-blocking)"
fi

echo ""
echo "=== Gate Check Complete ==="
exit 0
