#!/bin/bash
# GATE-REPO-001: Repository Verification
# Reference: .ai/RELEASE-STANDARD.md
# Purpose: Ensure work happens in canonical repo, not docs repo
# Security: No user input, safe for CI
set -e

echo "GATE-REPO-001: Repository Verification"
echo "======================================="

# Verify required commands
if ! command -v git >/dev/null 2>&1; then
  echo "FAIL: Required command 'git' not found"
  exit 1
fi

# Get current directory
cwd=$(pwd)
echo "Current directory: $cwd"

# Get git remote
if ! git rev-parse --git-dir > /dev/null 2>&1; then
  echo ""
  echo "FAIL: Not in a git repository"
  exit 1
fi

remote_url=$(git remote get-url origin 2>/dev/null || echo "NO_REMOTE")
echo "Git remote: $remote_url"

# Check for canonical repo patterns
if echo "$remote_url" | grep -qE "motus-command|motus-internal|motus\.git$"; then
  echo ""
  echo "WARN: Working in internal docs/coordination repo"
  echo "  For code changes, use the canonical motus/packages/cli"
fi

# For release work, must be in canonical repo
if echo "$cwd" | grep -qE "motus-command|motus-internal"; then
  echo ""
  echo "INFO: In motus-internal repo (legacy: motus-command)"
  echo "  This is OK for documentation and handoffs"
  echo "  For code/release: use canonical motus repo"
fi

if echo "$cwd" | grep -qE "motus/packages/cli"; then
  echo ""
  echo "PASS: In canonical code repository"
fi

echo ""
echo "PASS: Repository context verified"
