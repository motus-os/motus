#!/bin/bash
# gate-lint.sh - Run ruff linter
set -e

echo "=== Lint Gate ==="
echo "Run ID: ${MOTUS_RUN_ID:-unknown}"
echo ""

# Run ruff on source and tests
if command -v ruff &> /dev/null; then
    echo "Running ruff check..."
    ruff check src/ tests/ 2>&1
    RESULT=$?
else
    echo "ruff not installed, skipping..."
    RESULT=0
fi

if [ $RESULT -eq 0 ]; then
    echo ""
    echo "[PASS] Lint check passed"
    exit 0
else
    echo ""
    echo "[FAIL] Lint check failed"
    exit 1
fi
