#!/bin/bash
# GATE-MIG-001: Migration Safety Scan
# Reference: .ai/RELEASE-STANDARD.md
# Purpose: Prevent destructive or seeded data migrations from shipping
set -e

echo "GATE-MIG-001: Migration Safety Scan"
echo "==================================="

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="${REPO_ROOT:-${MOTUS_REPO_ROOT:-$(cd "$SCRIPT_DIR/../.." && pwd)}}"
MIGRATIONS_DIR="${MIGRATIONS_DIR:-$REPO_ROOT/packages/cli/migrations}"

if [ ! -d "$MIGRATIONS_DIR" ]; then
  echo "SKIP: migrations directory not found: $MIGRATIONS_DIR"
  exit 0
fi

python3 - "$MIGRATIONS_DIR" <<'PY'
import re
import sys
from pathlib import Path

migrations_dir = Path(sys.argv[1])
failures = []

def strip_sql_comments(text: str) -> str:
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("--"):
            continue
        if "--" in line:
            line = line.split("--", 1)[0]
        lines.append(line)
    return "\n".join(lines)

for path in sorted(migrations_dir.glob("*.sql")):
    raw = path.read_text(encoding="utf-8", errors="ignore")

    # Block seeding roadmap items via migrations
    if re.search(r"\bINSERT\s+INTO\s+roadmap_items\b", raw, flags=re.IGNORECASE):
        failures.append(f"{path.name}: roadmap_items insert detected (seed data not allowed)")

    cleaned = strip_sql_comments(raw)
    statements = [s.strip() for s in cleaned.split(";") if s.strip()]

    for stmt in statements:
        # Fail UPDATE/DELETE statements without WHERE
        if re.match(r"^(UPDATE|DELETE)\b", stmt, flags=re.IGNORECASE):
            if not re.search(r"\bWHERE\b", stmt, flags=re.IGNORECASE):
                head = " ".join(stmt.split())[:120]
                failures.append(f"{path.name}: {head}... (missing WHERE)")

if failures:
    print("FAIL: Migration safety scan failed")
    for item in failures:
        print(f"  - {item}")
    sys.exit(1)

print("PASS: Migration safety scan clean")
PY
