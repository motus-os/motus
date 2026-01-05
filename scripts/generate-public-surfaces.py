#!/usr/bin/env python3
"""Generate README and website messaging JSON from messaging.yaml."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
MESSAGING_YAML = REPO_ROOT / "packages" / "cli" / "docs" / "website" / "messaging.yaml"
MESSAGING_JSON = REPO_ROOT / "packages" / "website" / "src" / "data" / "messaging.json"
ROOT_README = REPO_ROOT / "README.md"
CLI_README = REPO_ROOT / "packages" / "cli" / "README.md"

GENERATED_HEADER = (
    "<!-- GENERATED FILE - DO NOT EDIT DIRECTLY -->\n"
    "<!-- Edit packages/cli/docs/website/messaging.yaml instead -->\n\n"
)


def _load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _render_badges(badges: Iterable[dict]) -> str:
    lines = []
    for badge in badges:
        badge_type = badge.get("type")
        if badge_type == "license":
            value = badge.get("value", "")
            color = badge.get("color", "blue")
            url = badge.get("url", "LICENSE")
            image = f"https://img.shields.io/badge/license-{value}-{color}.svg"
            lines.append(f"[![License]({image})]({url})")
        elif badge_type == "pypi":
            package = badge.get("package", "motusos")
            image = f"https://img.shields.io/pypi/v/{package}"
            link = f"https://pypi.org/project/{package}/"
            lines.append(f"[![PyPI]({image})]({link})")
        elif badge_type == "downloads":
            package = badge.get("package", "motusos")
            image = f"https://img.shields.io/pypi/dm/{package}"
            link = f"https://pypi.org/project/{package}/"
            lines.append(f"[![Downloads]({image})]({link})")
    return "\n".join(lines)


def _find_section(sections: list[dict], section_id: str) -> dict | None:
    for section in sections:
        if section.get("id") == section_id:
            return section
    return None


def _render_quickstart(steps: list[dict]) -> str:
    commands = [step["command"] for step in steps if step.get("command")]
    expected = [step["expected"] for step in steps if step.get("expected")]
    output = ["## Quickstart", "", "```bash"]
    output.extend(commands)
    output.append("```")
    if expected:
        output.append("")
        output.append("Expected:")
        output.extend([f"- {line}" for line in expected])
    return "\n".join(output)


def _render_install(steps: list[dict]) -> str:
    install = next((step for step in steps if step.get("id") == "install"), None)
    if not install:
        return ""
    return "\n".join([
        "## Install",
        "",
        "```bash",
        install["command"],
        "```",
        f"Expected: {install.get('expected', '')}",
    ])


def _render_benefits(benefits: list[dict]) -> str:
    lines = ["## Benefits", ""]
    for benefit in benefits:
        lines.append(f"- **{benefit.get('headline', '').strip()}**: {benefit.get('detail', '').strip()}")
    return "\n".join(lines)


def _render_links(links: dict) -> str:
    items = {
        "Website": links.get("website"),
        "Get Started": links.get("get_started"),
        "How It Works": links.get("how_it_works"),
        "Docs": links.get("docs"),
        "PyPI": links.get("pypi"),
        "GitHub": links.get("github"),
    }
    lines = ["## Links", ""]
    for label, url in items.items():
        if url:
            lines.append(f"- {label}: {url}")
    return "\n".join(lines)


def _render_demo(demo: dict, section_cfg: dict | None) -> str:
    if not section_cfg or not section_cfg.get("include", False):
        return ""
    status = demo.get("status", "none")
    asset_path = demo.get("asset_path")
    alt = demo.get("alt", "Motus demo")
    if status == "real" and asset_path:
        return "\n".join([
            "## Demo",
            "",
            f"![{alt}]({asset_path})",
        ])
    if status == "placeholder":
        return "\n".join([
            "## Demo",
            "",
            "_Demo asset coming soon (target)._",
        ])
    return ""


def _render_readme(messaging: dict) -> str:
    sections = messaging.get("readme_sections", [])
    section_ids = {section["id"]: section for section in sections if section.get("include", False)}

    one_liner = messaging.get("one_liner", "")
    tagline = messaging.get("tagline", "")
    quickstart = messaging.get("quickstart", {})
    steps = quickstart.get("steps", [])

    parts = [
        GENERATED_HEADER,
        "# Motus",
        "",
        f"> {one_liner}",
        f"> {tagline}",
        "",
    ]

    badges = _render_badges(messaging.get("badges", []))
    if badges:
        parts.append(badges)
        parts.append("")

    demo_block = _render_demo(messaging.get("demo", {}), section_ids.get("demo_gif"))
    if demo_block:
        parts.append(demo_block)
        parts.append("")

    if section_ids.get("install"):
        parts.append(_render_install(steps))
        parts.append("")

    if section_ids.get("quickstart"):
        parts.append(_render_quickstart(steps))
        parts.append("")

    if section_ids.get("benefits"):
        parts.append(_render_benefits(messaging.get("benefits", [])))
        parts.append("")

    if section_ids.get("links"):
        parts.append(_render_links(messaging.get("links", {})))
        parts.append("")

    if section_ids.get("license"):
        license_url = messaging.get("links", {}).get("license", "LICENSE")
        parts.append("## License\n\nMotus Community Source License (MCSL). See {}.".format(license_url))

    return "\n".join([part for part in parts if part is not None]).strip() + "\n"


def main() -> None:
    if not MESSAGING_YAML.exists():
        raise FileNotFoundError(f"Missing messaging.yaml at {MESSAGING_YAML}")

    messaging = _load_yaml(MESSAGING_YAML)

    MESSAGING_JSON.parent.mkdir(parents=True, exist_ok=True)
    MESSAGING_JSON.write_text(json.dumps(messaging, indent=2) + "\n", encoding="utf-8")

    readme = _render_readme(messaging)
    ROOT_README.write_text(readme, encoding="utf-8")
    CLI_README.write_text(readme, encoding="utf-8")

    print("Done. Generated README files and messaging.json from messaging.yaml")


if __name__ == "__main__":
    main()
