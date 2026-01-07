#!/usr/bin/env python3
"""Ensure sqlite3.connect is only used in approved modules."""
from __future__ import annotations

import re
import sys
from pathlib import Path


ALLOWED = {
    "src/motus/cli/help.py",
    "src/motus/commands/db_cmd.py",
    "src/motus/context_cache/store.py",
    "src/motus/coordination/api/lease_store.py",
    "src/motus/core/database_connection.py",
    "src/motus/governance/core.py",
    "src/motus/knowledge/store.py",
    "src/motus/session_store_core.py",
}

PATTERN = re.compile(r"\bsqlite3\.connect\b")


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    src_root = repo_root / "src"
    if not src_root.exists():
        print("ERROR: src/ not found", file=sys.stderr)
        return 2

    violations = []
    for path in sorted(src_root.rglob("*.py")):
        rel_path = path.relative_to(repo_root).as_posix()
        if rel_path in ALLOWED:
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except OSError as exc:
            print(f"WARN: failed to read {rel_path}: {exc}", file=sys.stderr)
            continue
        if PATTERN.search(content):
            violations.append(rel_path)

    if violations:
        print("ERROR: sqlite3.connect used outside allowlist", file=sys.stderr)
        for path in violations:
            print(f"  - {path}", file=sys.stderr)
        return 1

    print("OK: sqlite3.connect usage within allowlist")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
