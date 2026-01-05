#!/usr/bin/env python3
"""
Bidirectional CLI ↔ Documentation Audit

This script enforces consistency between CLI commands and website documentation:
- CLI → Docs: Every user-facing command should be documented
- Docs → CLI: Every documented command must exist in the CLI

Run this in CI to prevent phantom commands (documented but don't exist)
and undocumented features (exist but not documented).

Usage:
    python scripts/audit-cli-docs.py [--fix] [--verbose]

Exit codes:
    0 - All commands in sync
    1 - Phantom commands found (docs reference non-existent commands)
    2 - Undocumented commands found (CLI has commands not in docs)
    3 - Both issues found
"""

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import NamedTuple


class Command(NamedTuple):
    """A CLI command with its full path."""
    path: tuple[str, ...]  # e.g., ('motus', 'work', 'claim')
    description: str

    @property
    def full_path(self) -> str:
        return ' '.join(self.path)

    def matches(self, pattern: str) -> bool:
        """Check if this command matches a documentation pattern."""
        return self.full_path == pattern or pattern in self.full_path


class AuditResult(NamedTuple):
    """Result of the audit."""
    cli_commands: set[str]
    doc_commands: set[str]
    phantom_commands: set[str]  # In docs but not CLI
    undocumented_commands: set[str]  # In CLI but not docs


def discover_cli_commands(base_cmd: str = 'motus', manifest_path: Path | None = None) -> set[str]:
    """
    Discover CLI commands from manifest or --help.

    If manifest exists, use it (fast, reliable).
    Otherwise, parse --help output (slower, for verification).

    Returns set of full command paths like:
    - 'motus work claim'
    - 'motus init'
    - 'motus claims list'
    """
    # Try manifest first (preferred - fast and authoritative)
    if manifest_path and manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
        return set(manifest.get('commands', []))

    # Fallback: parse --help (two levels deep only for speed)
    commands = set()

    # Get top-level commands
    env = os.environ.copy()
    env["MC_HELP_TIER"] = "3"
    try:
        result = subprocess.run(
            [base_cmd, '--help'],
            capture_output=True,
            text=True,
            timeout=10,
            env=env,
        )
        help_text = result.stdout + result.stderr
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        print(f"  Warning: Could not run {base_cmd} --help: {e}")
        return commands

    # Parse top-level commands from help
    top_level = []
    # Skip lines that are env vars or tier headers
    skip_patterns = ['MC_', 'options', 'positional', 'arguments', 'Usage', 'Try', 'Environment', 'Exit']
    for line in help_text.split('\n'):
        # Match lines like "  command    description"
        match = re.match(r'^\s{2}([a-z][a-z0-9-]*)\s{2,}', line)
        if match:
            cmd = match.group(1)
            if not any(skip in cmd or skip in line for skip in skip_patterns):
                top_level.append(cmd)
                commands.add(f"{base_cmd} {cmd}")

    # Get subcommands for known command groups
    # Include 'work' even if not in top-level (it exists but may be hidden)
    subcommand_groups = ['work', 'claims', 'policy', 'standards']
    for group in subcommand_groups:
        try:
            result = subprocess.run(
                [base_cmd, group, '--help'],
                capture_output=True,
                text=True,
                timeout=5,
                env=env,
            )
            group_help = result.stdout + result.stderr

            # If command exists, add the group command itself
            if result.returncode == 0 or 'usage:' in group_help.lower():
                commands.add(f"{base_cmd} {group}")

            # Parse subcommands from {a,b,c} pattern
            match = re.search(r'\{([^}]+)\}', group_help)
            if match:
                for sub in match.group(1).split(','):
                    sub = sub.strip()
                    if sub:
                        commands.add(f"{base_cmd} {group} {sub}")
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

    return commands


def extract_doc_commands(website_dir: Path) -> set[str]:
    """
    Extract all command references from website documentation.

    Scans:
    - tutorial.yaml
    - *.astro pages
    - *.js data files
    - *.json data files

    Returns set of command patterns found.
    """
    commands = set()

    # Patterns to match command references
    patterns = [
        # Quoted commands: "motus work claim"
        r'"(motus\s+\w+(?:\s+\w+)*)"',
        # Code blocks: `motus work claim`
        r'`(motus\s+\w+(?:\s+\w+)*)`',
        # YAML command fields: command: "motus work claim"
        r'command:\s*["\']?(motus\s+\w+(?:\s+\w+)*)["\']?',
        # Shell examples: $ motus work claim
        r'\$\s*(motus\s+\w+(?:\s+\w+)*)',
    ]

    # Files to scan
    file_patterns = ['**/*.yaml', '**/*.yml', '**/*.astro', '**/*.js', '**/*.json', '**/*.md']

    for pattern in file_patterns:
        for file_path in website_dir.rglob(pattern.replace('**/', '')):
            if 'node_modules' in str(file_path):
                continue
            if '.astro' in str(file_path.parent):
                continue
            if not file_path.is_file():
                continue

            try:
                content = file_path.read_text()
            except (UnicodeDecodeError, PermissionError, IsADirectoryError):
                continue

            for regex in patterns:
                for match in re.finditer(regex, content, re.MULTILINE):
                    cmd = match.group(1).strip()
                    # Normalize: remove extra whitespace
                    cmd = ' '.join(cmd.split())
                    # Skip variable interpolations
                    if '${' in cmd or '$(' in cmd:
                        continue
                    # Skip example patterns with arguments (e.g., "motus work claim DEMO-001")
                    # Keep only the command path portion
                    parts = cmd.split()
                    if len(parts) > 2 and parts[0] == 'motus':
                        # For subcommands, keep only motus <group> <subcommand>
                        # Filter out any part that looks like an argument (has - or uppercase)
                        clean_parts = [parts[0]]  # 'motus'
                        for p in parts[1:]:
                            if p[0].isupper() or p.startswith('-') or p.startswith('"'):
                                break
                            clean_parts.append(p)
                        cmd = ' '.join(clean_parts)
                    commands.add(cmd)

    return commands


def load_known_gaps(website_dir: Path) -> dict:
    """
    Load known gaps from audit-known-gaps.json.

    This file allows teams to acknowledge gaps that are:
    - Planned for future releases
    - Intentionally undocumented (internal commands)
    - False positives
    """
    gaps_file = website_dir / 'audit-known-gaps.json'
    if not gaps_file.exists():
        return {'phantom': set(), 'undocumented': set(), 'internal': set()}

    data = json.loads(gaps_file.read_text())

    # Parse phantom commands (can be string or object with 'command' key)
    phantom = set()
    for item in data.get('phantom', []):
        if isinstance(item, str):
            phantom.add(item)
        elif isinstance(item, dict) and 'command' in item:
            phantom.add(item['command'])

    # Parse undocumented (simple strings)
    undocumented = set(data.get('undocumented', []))

    # Parse internal commands
    internal = set(data.get('internal', []))

    # Parse tier 2+ commands (also excluded from undocumented warnings)
    tier_2_plus = set(data.get('tier_2_plus', []))

    # Parse documented_elsewhere commands
    documented_elsewhere = set()
    for item in data.get('documented_elsewhere', []):
        if isinstance(item, str):
            documented_elsewhere.add(item)
        elif isinstance(item, dict) and 'command' in item:
            documented_elsewhere.add(item['command'])

    return {
        'phantom': phantom,
        'undocumented': undocumented | internal | tier_2_plus | documented_elsewhere,
        'internal': internal | tier_2_plus
    }


def run_audit(website_dir: Path, verbose: bool = False, manifest_path: Path | None = None) -> AuditResult:
    """Run the full bidirectional audit."""

    print("=" * 60)
    print("CLI ↔ Documentation Audit")
    print("=" * 60)

    # Step 1: Discover CLI commands
    print("\n[1/3] Discovering CLI commands...")
    cli_commands = discover_cli_commands('motus', manifest_path)
    if verbose:
        print(f"  Found {len(cli_commands)} CLI commands:")
        for cmd in sorted(cli_commands):
            print(f"    - {cmd}")
    else:
        print(f"  Found {len(cli_commands)} CLI commands")

    # Step 2: Extract documented commands
    print("\n[2/3] Extracting documented commands...")
    doc_commands = extract_doc_commands(website_dir)
    if verbose:
        print(f"  Found {len(doc_commands)} documented commands:")
        for cmd in sorted(doc_commands):
            print(f"    - {cmd}")
    else:
        print(f"  Found {len(doc_commands)} documented commands")

    # Step 3: Load known gaps
    known_gaps = load_known_gaps(website_dir)
    internal_commands = set(known_gaps.get('internal', []))
    known_phantom = set(known_gaps.get('phantom', []))
    known_undocumented = set(known_gaps.get('undocumented', []))

    # Step 4: Compare
    print("\n[3/3] Comparing...")

    # Phantom commands: documented but don't exist
    phantom_commands = doc_commands - cli_commands - known_phantom

    # Undocumented commands: exist but not documented (excluding internal)
    user_facing_cli = cli_commands - internal_commands
    undocumented_commands = user_facing_cli - doc_commands - known_undocumented

    return AuditResult(
        cli_commands=cli_commands,
        doc_commands=doc_commands,
        phantom_commands=phantom_commands,
        undocumented_commands=undocumented_commands
    )


def print_report(result: AuditResult) -> int:
    """Print the audit report and return exit code."""

    print("\n" + "=" * 60)
    print("AUDIT REPORT")
    print("=" * 60)

    exit_code = 0

    # Phantom commands (CRITICAL - blocks release)
    if result.phantom_commands:
        print("\n❌ PHANTOM COMMANDS (documented but don't exist):")
        print("   These commands are referenced in docs but don't exist in CLI.")
        print("   This WILL confuse users. Fix before release.\n")
        for cmd in sorted(result.phantom_commands):
            print(f"   - {cmd}")
        exit_code |= 1
    else:
        print("\n✅ No phantom commands (all documented commands exist)")

    # Undocumented commands (WARNING - should document)
    if result.undocumented_commands:
        print("\n⚠️  UNDOCUMENTED COMMANDS (exist but not documented):")
        print("   These commands exist but aren't documented on the website.")
        print("   Consider adding them or marking as internal.\n")
        for cmd in sorted(result.undocumented_commands):
            print(f"   - {cmd}")
        exit_code |= 2
    else:
        print("\n✅ No undocumented user-facing commands")

    # Summary
    print("\n" + "-" * 60)
    print("SUMMARY")
    print("-" * 60)
    print(f"  CLI commands:          {len(result.cli_commands)}")
    print(f"  Documented commands:   {len(result.doc_commands)}")
    print(f"  Phantom (BLOCK):       {len(result.phantom_commands)}")
    print(f"  Undocumented (WARN):   {len(result.undocumented_commands)}")

    if exit_code == 0:
        print("\n🎉 All commands are in sync!")
    elif exit_code == 1:
        print("\n🚨 BLOCKING: Fix phantom commands before release")
    elif exit_code == 2:
        print("\n⚠️  WARNING: Document new commands or mark as internal")
    else:
        print("\n🚨 BLOCKING + WARNING: Multiple issues found")

    return exit_code


def generate_known_gaps_template(result: AuditResult, website_dir: Path):
    """Generate a template for audit-known-gaps.json."""

    template = {
        "_comment": "Commands acknowledged as gaps. Review periodically.",
        "phantom": list(sorted(result.phantom_commands)),
        "undocumented": [],
        "internal": [
            "motus mcp",  # MCP server - not user-facing
            "motus sync",  # Internal sync - not user-facing
        ]
    }

    gaps_file = website_dir / 'audit-known-gaps.json'
    print(f"\n📝 Generated template at: {gaps_file}")
    print("   Review and edit to acknowledge intentional gaps.\n")
    gaps_file.write_text(json.dumps(template, indent=2))


def main():
    parser = argparse.ArgumentParser(description='Bidirectional CLI ↔ Docs Audit')
    parser.add_argument('--verbose', '-v', action='store_true', help='Show all commands')
    parser.add_argument('--fix', action='store_true', help='Generate known-gaps template')
    parser.add_argument('--website-dir', type=Path, default=Path('packages/website'),
                        help='Path to website package')
    parser.add_argument('--manifest', type=Path, default=None,
                        help='Path to CLI command manifest (optional, speeds up audit)')
    args = parser.parse_args()

    # Resolve website directory
    website_dir = args.website_dir
    if not website_dir.is_absolute():
        # Try relative to current dir, then script dir
        if not website_dir.exists():
            script_dir = Path(__file__).parent.parent
            website_dir = script_dir / args.website_dir

    if not website_dir.exists():
        print(f"❌ Website directory not found: {website_dir}")
        sys.exit(1)

    # Run audit
    result = run_audit(website_dir, verbose=args.verbose, manifest_path=args.manifest)

    # Print report
    exit_code = print_report(result)

    # Generate template if requested
    if args.fix and (result.phantom_commands or result.undocumented_commands):
        generate_known_gaps_template(result, website_dir)

    sys.exit(exit_code)


if __name__ == '__main__':
    main()
