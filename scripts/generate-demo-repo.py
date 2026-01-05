#!/usr/bin/env python3
"""Generate a demo repository from the website tutorial YAML."""
from __future__ import annotations

import argparse
import re
import shutil
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
TUTORIAL_YAML = REPO_ROOT / "packages" / "website" / "src" / "data" / "tutorial.yaml"
TEMPLATE_PATH = REPO_ROOT / "packages" / "website" / "templates" / "demo-repo-readme.md.jinja"


def _load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _render_template(template: str, context: dict[str, str]) -> str:
    def replace(match: re.Match[str]) -> str:
        key = match.group(1).strip()
        return context.get(key, "")

    return re.sub(r"\{\{\s*([^}]+)\s*\}\}", replace, template)


def _collect_files(tutorial: dict) -> list[tuple[str, str]]:
    files: list[tuple[str, str]] = []
    for feature in tutorial.get("features", []):
        for step in feature.get("steps", []):
            if step.get("type") == "file":
                files.append((step["path"], step["content"]))
    return files


def _tutorial_summary(tutorial: dict) -> str:
    lines: list[str] = []
    for feature in tutorial.get("features", []):
        lines.append(f"### {feature.get('title', 'Feature')}")
        for step in feature.get("steps", []):
            if step.get("type") == "command":
                lines.append(f"- `{step['command']}`")
        lines.append("")
    return "\n".join(lines).strip()


def _files_list(files: list[tuple[str, str]]) -> str:
    return "\n".join([f"- `{path}`" for path, _ in files])


def _write_static_files(output_dir: Path, demo_repo: dict) -> None:
    static_files = demo_repo.get("static_files", [])
    for entry in static_files:
        rel_path = entry.get("path")
        if not rel_path:
            continue
        target = output_dir / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        if "content" in entry:
            target.write_text(entry["content"], encoding="utf-8")
        elif "template" in entry:
            template_path = TEMPLATE_PATH.parent / entry["template"]
            template = template_path.read_text(encoding="utf-8")
            context = entry.get("context", {})
            target.write_text(_render_template(template, context), encoding="utf-8")


def generate_demo(output_dir: Path, force: bool) -> None:
    tutorial = _load_yaml(TUTORIAL_YAML)
    demo_repo = tutorial.get("demo_repo", {})
    if not demo_repo:
        raise SystemExit("tutorial.yaml missing demo_repo configuration")

    if output_dir.exists():
        if not force:
            raise SystemExit(f"Output directory already exists: {output_dir}")
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    files = _collect_files(tutorial)
    for rel_path, content in files:
        target = output_dir / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    readme_context = {
        "description": demo_repo.get("description", "").strip(),
        "validated_against": tutorial.get("validated_against", ""),
        "tutorial_summary": _tutorial_summary(tutorial),
        "files_list": _files_list(files),
    }
    readme = _render_template(template, readme_context)
    (output_dir / "README.md").write_text(readme, encoding="utf-8")

    # Write static files (requirements, gitignore)
    static_files = demo_repo.get("static_files", [])
    if static_files:
        for entry in static_files:
            if "template" in entry:
                entry["context"] = readme_context
        _write_static_files(output_dir, demo_repo)

    print(f"Demo repo generated at {output_dir}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Motus demo repo from tutorial.yaml.")
    parser.add_argument(
        "--output",
        default=str(REPO_ROOT / "dist" / "motus-demo-app"),
        help="Output directory for the demo repo.",
    )
    parser.add_argument("--force", action="store_true", help="Overwrite output directory if it exists.")
    args = parser.parse_args()

    output_dir = Path(args.output).resolve()
    generate_demo(output_dir, args.force)


if __name__ == "__main__":
    main()
