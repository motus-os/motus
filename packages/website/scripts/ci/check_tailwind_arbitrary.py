#!/usr/bin/env python3
"""Fail CI if new Tailwind arbitrary values are not allowlisted."""

from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
ALLOWLIST = ROOT / "standards" / "tailwind-arbitrary-allowlist.txt"

VALID_EXTENSIONS = {".astro", ".md", ".mdx", ".html", ".js", ".ts", ".jsx", ".tsx", ".css"}
CLASS_ATTR_RE = re.compile(r"class(?:Name)?\\s*=\\s*(?P<value>\"[^\"]*\"|'[^']*'|\\{[^}]*\\})", re.S)
CLASS_LIST_RE = re.compile(r"class:list\\s*=\\s*\\{(?P<value>[^}]*)\\}", re.S)
STRING_RE = re.compile(r"['\"]([^'\"]+)['\"]")
ARBITRARY_RE = re.compile(r".*\\[.+\\].*")


def _load_allowlist() -> set[str]:
    if not ALLOWLIST.exists():
        raise FileNotFoundError("standards/tailwind-arbitrary-allowlist.txt missing")
    entries: set[str] = set()
    for line in ALLOWLIST.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        entries.add(line)
    return entries


def _extract_string_literals(value: str) -> list[str]:
    tokens: list[str] = []
    for match in STRING_RE.finditer(value):
        tokens.extend(match.group(1).split())
    return tokens


def _extract_class_tokens(content: str) -> list[str]:
    tokens: list[str] = []
    for match in CLASS_ATTR_RE.finditer(content):
        value = match.group("value").strip()
        if value.startswith("{") and value.endswith("}"):
            tokens.extend(_extract_string_literals(value))
        else:
            tokens.extend(value.strip("'\"").split())
    for match in CLASS_LIST_RE.finditer(content):
        tokens.extend(_extract_string_literals(match.group("value")))
    return tokens


def _scan_sources() -> set[str]:
    found: set[str] = set()
    if not SRC.exists():
        return found
    for path in SRC.rglob("*"):
        if path.suffix not in VALID_EXTENSIONS:
            continue
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for token in _extract_class_tokens(content):
            if ARBITRARY_RE.match(token):
                found.add(token)
    return found


def main() -> int:
    try:
        allowlisted = _load_allowlist()
    except FileNotFoundError as exc:
        print(f"Tailwind arbitrary check failed: {exc}", file=sys.stderr)
        return 1

    found = _scan_sources()
    unknown = sorted(value for value in found if value not in allowlisted)

    if unknown:
        print("Tailwind arbitrary check failed:", file=sys.stderr)
        print("  New arbitrary values detected (add to allowlist if intentional):", file=sys.stderr)
        for value in unknown:
            print(f"  - {value}", file=sys.stderr)
        return 1

    print("Tailwind arbitrary check: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
