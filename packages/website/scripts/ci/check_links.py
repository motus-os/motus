#!/usr/bin/env python3
"""Fail CI on broken internal links in website sources."""

from __future__ import annotations

import posixpath
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
PAGES = SRC / "pages"
PUBLIC = ROOT / "public"

VALID_EXTENSIONS = {".astro", ".md", ".mdx", ".html"}
HREF_RE = re.compile(r"href\\s*[:=]\\s*(?:\\{)?(?P<quote>['\"`])(?P<url>[^'\"`]+)(?P=quote)")
SKIP_PREFIXES = (
    "http://",
    "https://",
    "mailto:",
    "tel:",
    "javascript:",
    "data:",
    "//",
)


def _normalize_path(path: str) -> str:
    normalized = posixpath.normpath(path)
    if not normalized.startswith("/"):
        normalized = "/" + normalized
    return normalized


def _page_route(path: Path) -> str:
    rel = path.relative_to(PAGES).with_suffix("")
    parts = rel.parts
    if not parts:
        return "/"
    if parts[-1] == "index":
        route = "/" + "/".join(parts[:-1])
    else:
        route = "/" + "/".join(parts)
    return route if route != "/" else "/"


def _build_routes() -> set[str]:
    routes: set[str] = set()
    for path in PAGES.rglob("*"):
        if path.suffix not in VALID_EXTENSIONS:
            continue
        route = _page_route(path)
        if route == "/":
            routes.add("/")
        else:
            route = route.rstrip("/")
            routes.add(route)
            routes.add(route + "/")
    return routes


def _build_public_paths() -> set[str]:
    public_paths: set[str] = set()
    if not PUBLIC.exists():
        return public_paths
    for path in PUBLIC.rglob("*"):
        if path.is_file():
            rel = path.relative_to(PUBLIC).as_posix()
            public_paths.add("/" + rel)
    return public_paths


def _clean_url(url: str) -> str:
    url = url.strip()
    url = url.replace("${base}/", "/").replace("${base}", "/")
    if "{" in url or "}" in url:
        return ""
    url = url.split("#", 1)[0]
    url = url.split("?", 1)[0]
    return url


def _resolve_relative(url: str, base_route: str) -> str:
    combined = posixpath.join(base_route, url)
    return _normalize_path(combined)


def main() -> int:
    if not SRC.exists() or not PAGES.exists():
        print("Link check: website source not found.")
        return 1

    routes = _build_routes()
    public_paths = _build_public_paths()
    errors: list[tuple[str, str]] = []

    for path in SRC.rglob("*"):
        if path.suffix not in VALID_EXTENSIONS:
            continue
        content = path.read_text(encoding="utf-8", errors="ignore")
        base_route = "/"
        if path.is_relative_to(PAGES):
            route = _page_route(path)
            if route == "/":
                base_route = "/"
            else:
                base_route = route.rsplit("/", 1)[0] or "/"

        for match in HREF_RE.finditer(content):
            url = _clean_url(match.group("url"))
            if not url or url == "#":
                continue
            if url.startswith(SKIP_PREFIXES):
                continue

            if url.startswith("/"):
                candidate = _normalize_path(url)
            else:
                candidate = _resolve_relative(url, base_route)

            if candidate in routes or candidate.rstrip("/") in routes:
                continue
            if candidate in public_paths:
                continue
            errors.append((str(path.relative_to(SRC)), candidate))

    if errors:
        print("Broken internal links detected:")
        for source, target in errors:
            print(f"  - {source}: {target}")
        return 1
    print("Link check: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
