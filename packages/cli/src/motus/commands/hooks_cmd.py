# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Hook installation commands."""

import json
from pathlib import Path

from rich.console import Console
from rich.markup import escape

console = Console()

# Claude settings file
CLAUDE_SETTINGS = Path.home() / ".claude" / "settings.json"


def get_mc_hook_config() -> dict:
    """Generate Motus hook configuration for Claude Code."""
    return {
        "hooks": {
            "SessionStart": [
                {
                    "matcher": "*",
                    "hooks": [
                        {
                            "type": "command",
                            "command": 'python3 -c "from motus.hooks import session_start_hook; session_start_hook()"',
                            "timeout": 5000,
                        }
                    ],
                }
            ],
            "UserPromptSubmit": [
                {
                    "matcher": "*",
                    "hooks": [
                        {
                            "type": "command",
                            "command": 'python3 -c "from motus.hooks import user_prompt_hook; user_prompt_hook()"',
                            "timeout": 3000,
                        }
                    ],
                }
            ],
        }
    }


def install_hooks_command():
    """Install Motus hooks into Claude Code settings."""
    console.print("[bold]Installing Motus hooks...[/bold]")

    # Ensure Claude directory exists
    CLAUDE_SETTINGS.parent.mkdir(parents=True, exist_ok=True)

    # Load existing settings
    settings = {}
    if CLAUDE_SETTINGS.exists():
        try:
            settings = json.loads(CLAUDE_SETTINGS.read_text())
        except json.JSONDecodeError:
            console.print(
                "[yellow]Warning: Existing settings.json is invalid, creating new one.[/yellow]"
            )

    # Get hook config
    hook_config = get_mc_hook_config()

    # Merge hooks
    if "hooks" not in settings:
        settings["hooks"] = {}

    for hook_type, hooks in hook_config["hooks"].items():
        if hook_type not in settings["hooks"]:
            settings["hooks"][hook_type] = []

        # Check if Motus hook already exists
        existing_commands = [
            h.get("hooks", [{}])[0].get("command", "") for h in settings["hooks"][hook_type]
        ]

        for hook in hooks:
            if "motus" not in " ".join(existing_commands):
                settings["hooks"][hook_type].append(hook)
                console.print(f"  [green]✓[/green] Added {escape(hook_type)} hook")
            else:
                console.print(
                    f"  [dim]- {escape(hook_type)} hook already exists[/dim]"
                )

    # Write updated settings
    CLAUDE_SETTINGS.write_text(json.dumps(settings, indent=2))

    console.print()
    console.print("[green]✓ Motus hooks installed![/green]")
    console.print("[dim]Restart Claude Code to activate.[/dim]")


def uninstall_hooks_command():
    """Remove Motus hooks from Claude Code settings."""
    console.print("[bold]Removing Motus hooks...[/bold]")

    if not CLAUDE_SETTINGS.exists():
        console.print("[yellow]No Claude settings found.[/yellow]")
        return

    try:
        settings = json.loads(CLAUDE_SETTINGS.read_text())
    except json.JSONDecodeError:
        console.print("[red]Error: Invalid settings.json[/red]")
        return

    if "hooks" not in settings:
        console.print("[yellow]No hooks configured.[/yellow]")
        return

    removed = 0
    for hook_type in list(settings["hooks"].keys()):
        original_count = len(settings["hooks"][hook_type])
        settings["hooks"][hook_type] = [
            h for h in settings["hooks"][hook_type] if "motus" not in str(h)
        ]
        removed += original_count - len(settings["hooks"][hook_type])

        # Clean up empty arrays
        if not settings["hooks"][hook_type]:
            del settings["hooks"][hook_type]

    # Clean up empty hooks object
    if not settings["hooks"]:
        del settings["hooks"]

    CLAUDE_SETTINGS.write_text(json.dumps(settings, indent=2))

    console.print(f"[green]✓ Removed {removed} Motus hooks[/green]")
