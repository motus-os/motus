#!/bin/bash
# GATE-PERF-001: Startup Time Baseline
# Reference: .ai/RELEASE-STANDARD.md
# Purpose: Catch import bloat before release
# Threshold: motus --version must complete in < 500ms
set -e

echo "GATE-PERF-001: Startup Time Baseline"
echo "====================================="

# Verify required commands
if ! command -v motus >/dev/null 2>&1; then
  echo "FAIL: motus command not found"
  exit 1
fi

# Configuration
MAX_MS=500
RUNS=3

echo "Threshold: ${MAX_MS}ms"
echo "Runs: $RUNS (taking median)"
echo ""

# Collect timing samples
times=()
for i in $(seq 1 $RUNS); do
  # Use Python for precise timing (portable, no bc dependency)
  elapsed=$(python3 -c "
import subprocess
import time

start = time.perf_counter()
subprocess.run(['motus', '--version'], capture_output=True)
end = time.perf_counter()
print(int((end - start) * 1000))
" 2>/dev/null)

  if [ -z "$elapsed" ]; then
    echo "FAIL: Could not measure startup time"
    exit 1
  fi

  times+=("$elapsed")
  echo "  Run $i: ${elapsed}ms"
done

# Calculate median using Python (no sort dependency issues)
median=$(python3 -c "
import sys
times = [${times[0]}, ${times[1]}, ${times[2]}]
times.sort()
print(times[len(times)//2])
")

echo ""
echo "Median: ${median}ms"

# Check threshold
if [ "$median" -gt "$MAX_MS" ]; then
  echo ""
  echo "FAIL: Startup time ${median}ms exceeds threshold ${MAX_MS}ms"
  echo ""
  echo "Likely causes:"
  echo "  1. Heavy imports at module level"
  echo "  2. Expensive initialization in __init__.py"
  echo "  3. Large data files loaded on import"
  echo ""
  echo "Debug with: python3 -X importtime -c 'import motus' 2>&1 | head -50"
  exit 1
fi

echo ""
echo "PASS: Startup time ${median}ms within threshold ${MAX_MS}ms"

# Also capture import breakdown for evidence
echo ""
echo "Top 10 slowest imports:"
python3 -X importtime -c "import motus" 2>&1 | sort -t: -k2 -n -r | head -10 || true

exit 0
