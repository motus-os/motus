#!/bin/bash
# GATE-WEB-001: Web UI Smoke Test
# Purpose: Verify web dashboard loads and responds
# Security: No user input, safe for CI
set -e

echo "=== GATE-WEB-001: Web UI Smoke Test ==="

PORT=4000
STARTUP_TIMEOUT=10
pid=""
tmpdir=""

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

# Cleanup handler - ensures background process is killed on any exit
cleanup() {
  if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
    kill "$pid" 2>/dev/null || true
    wait "$pid" 2>/dev/null || true
  fi
  if [ -n "$tmpdir" ] && [ -d "$tmpdir" ]; then
    rm -rf "$tmpdir"
  fi
}
trap cleanup EXIT INT TERM

# Verify required commands exist
for cmd in motus curl lsof; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "FAIL: Required command '$cmd' not found"
    exit 1
  fi
done

# Check if port is already in use
if lsof -i :"$PORT" >/dev/null 2>&1; then
  echo "WARN: Port $PORT already in use"
  echo "Checking if it's motus web..."
  if curl -s --max-time 5 "http://127.0.0.1:$PORT" | grep -qi "motus"; then
    echo "PASS: Motus web already running and responding"
    exit 0
  else
    echo "FAIL: Port $PORT in use by another process"
    lsof -i :"$PORT" 2>/dev/null || true
    exit 1
  fi
fi

# Isolate Motus directory and database for the gate
umask 077
tmpdir=$(mktemp -d)
export HOME="$tmpdir"
MOTUS_DIR="$HOME/.motus"
mkdir -p "$MOTUS_DIR"
export MOTUS_DATABASE__PATH="$MOTUS_DIR/coordination.db"
timeout_cmd 30 motus doctor --fix >/dev/null 2>&1 || true

# Start web server in background with timeout
echo "Starting motus web..."
timeout_cmd 60 motus web &
pid=$!

# Poll for server readiness instead of fixed sleep
echo "Waiting for server to start (max ${STARTUP_TIMEOUT}s)..."
for i in $(seq 1 "$STARTUP_TIMEOUT"); do
  if curl -s --max-time 2 "http://127.0.0.1:$PORT" >/dev/null 2>&1; then
    break
  fi
  if ! kill -0 "$pid" 2>/dev/null; then
    echo ""
    echo "FAIL: Web server crashed on startup"
    echo "Check logs for import errors or missing dependencies"
    exit 1
  fi
  sleep 1
done

# Check if server is still running after polling
if ! kill -0 "$pid" 2>/dev/null; then
  echo ""
  echo "FAIL: Web server crashed during startup"
  echo "Check logs for import errors or missing dependencies"
  exit 1
fi

# Check if page loads with expected content
echo "Testing HTTP response..."
response=$(curl -s --max-time 5 "http://127.0.0.1:$PORT" 2>/dev/null || echo "")
if [ -z "$response" ]; then
  echo ""
  echo "FAIL: No response from web server"
  exit 1
fi

# Verify response contains expected content (case-insensitive)
if ! echo "$response" | grep -qi "motus"; then
  echo ""
  echo "FAIL: Web UI response doesn't contain expected content"
  echo "Response may be an error page"
  exit 1
fi

echo "HTTP response: OK"

# Note: WebSocket check removed - curl cannot properly test WS upgrade
# Manual verification required for WebSocket functionality

# Cleanup handled by trap - no explicit kill needed here
wait $pid 2>/dev/null || true

echo ""
echo "PASS: Web UI loads successfully"
echo ""
echo "MANUAL VERIFICATION REQUIRED:"
echo "  1. Open http://127.0.0.1:4000"
echo "  2. Click a session"
echo "  3. Verify events load within 2 seconds (not stuck on 'Loading...')"
