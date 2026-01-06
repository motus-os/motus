#!/bin/bash
# gate-test.sh - Run pytest
set -e

echo "=== Test Gate ==="
echo "Run ID: ${MOTUS_RUN_ID:-unknown}"
echo ""

# Run pytest
if command -v pytest &> /dev/null; then
    echo "Running pytest..."
    pytest tests/ -q 2>&1
    RESULT=$?
else
    echo "pytest not installed, skipping..."
    RESULT=0
fi

if [ $RESULT -eq 0 ]; then
    echo ""
    echo "[PASS] Tests passed"
    exit 0
else
    echo ""
    echo "[FAIL] Tests failed"
    exit 1
fi
