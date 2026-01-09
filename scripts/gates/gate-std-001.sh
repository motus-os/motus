#!/bin/bash
# GATE-STD-001: Standards Registry Integrity
# Purpose: Ensure standards are seeded and versioned in coordination.db migrations
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${REPO_ROOT:-${MOTUS_REPO_ROOT:-$(cd "$SCRIPT_DIR/../.." && pwd)}}"

cd "$REPO_ROOT"

python3 packages/cli/scripts/ci/check_standards_registry.py
