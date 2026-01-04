# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""
Motus Config Loader.

Loads configuration from ~/.motus/config.json with env var overrides and defaults.
"""

import json
import os
from pathlib import Path
from typing import Any, Dict

from .config_schema import MCConfigSchema

# Default config file location
DEFAULT_CONFIG_PATH = Path.home() / ".motus" / "config.json"

# Environment variable mappings
ENV_VAR_MAP = {
    "MC_MOTUS_ENABLED": "motus_enabled",
    "MC_PROTOCOL_ENFORCEMENT": "protocol_enforcement",
    "MC_USE_SQLITE": "use_sqlite",
    "MC_GATE_TIMEOUT_SECONDS": "gate_timeout_seconds",
    "MC_EVIDENCE_DIR": "evidence_dir",
    "MC_DB_PATH": "db_path",
    "MC_CONTEXT_CACHE_DB_PATH": "context_cache_db_path",
    "MC_REPORTING_LEVEL": "reporting_level",
    "MC_METRICS_ENABLED": "metrics_enabled",
    "MC_ANTHROPIC_API_KEY": "anthropic_api_key",
    "MC_OPENAI_API_KEY": "openai_api_key",
    "MC_GITHUB_TOKEN": "github_token",
}


def _parse_env_value(value: str, field_type: type) -> Any:
    """Parse environment variable string to appropriate type."""
    if field_type is bool:
        return value.lower() in ("1", "true", "yes", "on")
    elif field_type is int:
        return int(value)
    elif field_type in (str, str | None):
        return value if value else None
    return value


def load_config(config_path: Path | None = None) -> MCConfigSchema:
    """Load configuration from file and environment variables.

    Priority (highest to lowest):
    1. Environment variables (MC_*)
    2. Config file (~/.motus/config.json)
    3. Schema defaults

    Args:
        config_path: Path to config file (default: ~/.motus/config.json)

    Returns:
        MCConfigSchema instance with merged configuration
    """
    if config_path is None:
        config_path = DEFAULT_CONFIG_PATH

    # Start with defaults
    config_dict: Dict[str, Any] = {}

    # Load from file if it exists
    if config_path.exists():
        try:
            with open(config_path, "r") as f:
                config_dict = json.load(f)
        except (json.JSONDecodeError, IOError):
            # If file is corrupted, use defaults
            pass

    # Create schema instance from file data (or defaults)
    config = MCConfigSchema.from_dict(config_dict)

    # Override with environment variables
    for env_var, field_name in ENV_VAR_MAP.items():
        env_value = os.environ.get(env_var)
        if env_value is not None:
            # Get field type from dataclass
            field_type = type(getattr(config, field_name))
            parsed_value = _parse_env_value(env_value, field_type)
            setattr(config, field_name, parsed_value)

    return config


def save_config(config: MCConfigSchema, config_path: Path | None = None) -> None:
    """Save configuration to file.

    Args:
        config: Configuration to save
        config_path: Path to save to (default: ~/.motus/config.json)
    """
    if config_path is None:
        config_path = DEFAULT_CONFIG_PATH

    # Ensure directory exists
    config_path.parent.mkdir(parents=True, exist_ok=True)

    # Write JSON
    with open(config_path, "w") as f:
        json.dump(config.to_dict(), f, indent=2)


def reset_config(config_path: Path | None = None) -> MCConfigSchema:
    """Reset configuration to defaults.

    Args:
        config_path: Path to config file (default: ~/.motus/config.json)

    Returns:
        New default configuration
    """
    if config_path is None:
        config_path = DEFAULT_CONFIG_PATH

    # Create default config
    config = MCConfigSchema()

    # Save it
    save_config(config, config_path)

    return config


def get_config_path() -> Path:
    """Get the path to the config file.

    Returns:
        Path to ~/.motus/config.json
    """
    return DEFAULT_CONFIG_PATH
