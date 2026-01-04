# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Config management command (`motus config`)."""

from __future__ import annotations

import json
import sys
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax

from ..config_loader import (
    get_config_path,
    load_config,
    reset_config,
    save_config,
)

console = Console()


def config_show() -> None:
    """Show current configuration as JSON.

    Note: API keys are excluded from output for security.
    If set via environment variables, shows "[set via env]".
    """
    from ..config_schema import SENSITIVE_FIELDS

    config = load_config()
    config_dict = config.to_dict()  # Excludes sensitive fields

    # Show indicator for sensitive fields that are set via env
    for field in SENSITIVE_FIELDS:
        value = getattr(config, field, None)
        if value is not None:
            config_dict[field] = "[set via env]"

    json_str = json.dumps(config_dict, indent=2)
    syntax = Syntax(json_str, "json", theme="monokai", line_numbers=False)
    console.print(Panel(syntax, title="[bold]Motus Configuration[/bold]"))


def config_get(key: str) -> None:
    """Get a single configuration value.

    Args:
        key: Configuration key to retrieve

    Note: Sensitive fields (API keys) show "[set via env]" instead of actual values.
    """
    from ..config_schema import SENSITIVE_FIELDS

    config = load_config()

    if not hasattr(config, key):
        console.print(f"[red]Error:[/red] Unknown config key: {key}")
        # Show all keys including sensitive ones
        all_keys = list(config.to_dict(include_sensitive=True).keys())
        console.print(f"\nValid keys: {', '.join(all_keys)}")
        sys.exit(1)

    value = getattr(config, key)

    # Don't reveal actual API key values
    if key in SENSITIVE_FIELDS:
        if value is not None:
            console.print("[set via env]")
        else:
            console.print("None")
    else:
        console.print(value)


def config_set(key: str, value: str) -> None:
    """Set a configuration value and save to file.

    Args:
        key: Configuration key to set
        value: Value to set (will be parsed to correct type)

    Note: Sensitive fields (API keys) cannot be set via config file.
          Use environment variables instead.
    """
    from ..config_schema import SENSITIVE_FIELDS

    config = load_config()

    if not hasattr(config, key):
        console.print(f"[red]Error:[/red] Unknown config key: {key}")
        all_keys = list(config.to_dict(include_sensitive=True).keys())
        console.print(f"\nValid keys: {', '.join(all_keys)}")
        sys.exit(1)

    # Prevent setting sensitive fields via config file
    if key in SENSITIVE_FIELDS:
        console.print(f"[red]Error:[/red] Cannot set {key} via config file (security risk)")
        console.print("\nUse environment variable instead:")
        env_var = f"MC_{key.upper()}"
        console.print(f"  export {env_var}=your-key-here")
        sys.exit(1)

    # Parse value to correct type
    current_value = getattr(config, key)
    parsed_value: Any = value

    if isinstance(current_value, bool):
        parsed_value = value.lower() in ("1", "true", "yes", "on")
    elif isinstance(current_value, int):
        try:
            parsed_value = int(value)
        except ValueError:
            console.print(f"[red]Error:[/red] Invalid integer value: {value}")
            sys.exit(1)
    elif current_value is None or isinstance(current_value, str):
        # Keep as string or set to None
        parsed_value = value if value.lower() != "none" else None

    # Set and save
    setattr(config, key, parsed_value)
    save_config(config)

    console.print(f"[green]✓[/green] Set {key} = {parsed_value}")
    console.print(f"[dim]Saved to {get_config_path()}[/dim]")


def config_reset() -> None:
    """Reset configuration to defaults."""
    reset_config()
    console.print("[green]✓[/green] Reset configuration to defaults")
    console.print(f"[dim]Saved to {get_config_path()}[/dim]")


def config_path() -> None:
    """Print the configuration file path."""
    console.print(get_config_path())


def config_command(args: list[str]) -> None:
    """Dispatch config subcommands.

    Usage:
        motus config show          - Show current configuration
        motus config get <key>     - Get single value
        motus config set <key> <value> - Set value
        motus config reset         - Reset to defaults
        motus config path          - Show config file path
    """
    if not args or args[0] in ("show", "-h", "--help"):
        if not args or args[0] == "show":
            config_show()
        else:
            console.print("[bold]motus config[/bold] - Manage Motus configuration\n")
            console.print("Usage:")
            console.print("  motus config show              Show current configuration")
            console.print("  motus config get <key>         Get single value")
            console.print("  motus config set <key> <value> Set value")
            console.print("  motus config reset             Reset to defaults")
            console.print("  motus config path              Show config file path")
        return

    subcommand_name = args[0]

    if subcommand_name == "get":
        if len(args) < 2:
            console.print("[red]Error:[/red] Missing key argument")
            console.print("Usage: motus config get <key>")
            sys.exit(1)
        config_get(args[1])

    elif subcommand_name == "set":
        if len(args) < 3:
            console.print("[red]Error:[/red] Missing key or value argument")
            console.print("Usage: motus config set <key> <value>")
            sys.exit(1)
        config_set(args[1], args[2])

    elif subcommand_name == "reset":
        config_reset()

    elif subcommand_name == "path":
        config_path()

    else:
        console.print(f"[red]Error:[/red] Unknown subcommand: {subcommand_name}")
        console.print("\nAvailable subcommands: show, get, set, reset, path")
        sys.exit(1)
