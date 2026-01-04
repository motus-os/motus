# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Layered configuration for Motus.

Configuration precedence (highest to lowest):
1. CLI arguments (--flag values)
2. Environment variables (MOTUS_*)
3. Project config (.motus/config.yaml)
4. User config (~/.config/motus/config.yaml)
5. System config (/etc/motus/config.yaml)
6. Defaults (hardcoded)
"""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import yaml

    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False

from .errors import ConfigError

CONFIG_LAYERS = [
    "cli",  # --flag values
    "environment",  # MOTUS_* env vars
    "project",  # .motus/config.yaml
    "user",  # ~/.config/motus/config.yaml
    "system",  # /etc/motus/config.yaml
    "defaults",  # Hardcoded
]


@dataclass
class ConfigValue:
    """Configuration value with source tracking."""

    value: Any
    source: str

    def __repr__(self) -> str:
        return f"ConfigValue(value={self.value!r}, source={self.source!r})"


class LayeredConfig:
    """Layered configuration manager.

    Example:
        config = LayeredConfig()

        # Get value (walks layers in priority order)
        db_path = config.get("database.path")

        # Set CLI override
        config.set_cli("database.path", "/tmp/test.db")

        # Explain where value comes from
        config.explain("database.path")
        # Returns: {'cli': '/tmp/test.db', 'environment': None, ...}
    """

    def __init__(self):
        """Initialize layered configuration."""
        self._layers: dict[str, dict] = {layer: {} for layer in CONFIG_LAYERS}
        self._load_defaults()
        self._load_file_layers()
        self._load_environment()

    def _load_defaults(self) -> None:
        """Load hardcoded defaults (lowest priority)."""
        self._layers["defaults"] = {
            "database.path": "~/.motus/coordination.db",
            "database.backup_dir": "~/.motus/backups",
            "federation.enabled": False,
            "federation.upstream_url": "",
            "federation.api_key": "",
            "quotas.enabled": True,
            "quotas.active_claims_per_agent": 50,
            "quotas.events_per_hour": 10000,
            "quotas.db_size_mb": 1000,
            "quotas.pending_outbox": 10000,
            "quotas.concurrent_sessions": 20,
            "telemetry.enabled": False,
            "health.check_interval_seconds": 300,
            "health.wal_warning_mb": 50,
            "health.wal_critical_mb": 100,
            "instance.name": "default",
            "protocol.version": 1,
        }

    def _load_file_layers(self) -> None:
        """Load configuration from YAML files."""
        if not YAML_AVAILABLE:
            return

        paths = {
            "project": Path(".motus/config.yaml"),
            "user": Path.home() / ".config/motus/config.yaml",
            "system": Path("/etc/motus/config.yaml"),
        }

        for layer, path in paths.items():
            if path.exists():
                try:
                    with open(path) as f:
                        data = yaml.safe_load(f) or {}
                        self._layers[layer] = self._flatten_dict(data)
                except Exception as e:
                    raise ConfigError(
                        f"[CONFIG-003] Failed to parse {path}: {e}"
                    ) from e

    def _load_environment(self) -> None:
        """Load configuration from environment variables.

        Environment variables are prefixed with MOTUS_ and use __ for nesting.
        Example: MOTUS_DATABASE__PATH -> database.path
        """
        for key, value in os.environ.items():
            if key.startswith("MOTUS_"):
                config_key = key[6:].lower().replace("__", ".")
                # Type coercion for boolean values
                if value.lower() in ("true", "yes", "1"):
                    value = True
                elif value.lower() in ("false", "no", "0"):
                    value = False
                # Type coercion for integers
                elif value.isdigit():
                    value = int(value)

                self._layers["environment"][config_key] = value

    def _flatten_dict(self, d: dict, parent_key: str = "") -> dict:
        """Flatten nested dict to dotted keys.

        Example:
            {'database': {'path': '/tmp/db'}} -> {'database.path': '/tmp/db'}
        """
        items = []
        for k, v in d.items():
            new_key = f"{parent_key}.{k}" if parent_key else k
            if isinstance(v, dict):
                items.extend(self._flatten_dict(v, new_key).items())
            else:
                items.append((new_key, v))
        return dict(items)

    def set_cli(self, key: str, value: Any) -> None:
        """Set CLI-level configuration (highest priority).

        Args:
            key: Configuration key (dotted notation)
            value: Configuration value
        """
        self._layers["cli"][key] = value

    def get(self, key: str, default: Any = None) -> ConfigValue:
        """Get configuration value (walks layers in priority order).

        Args:
            key: Configuration key (dotted notation)
            default: Default value if not found in any layer

        Returns:
            ConfigValue with value and source layer
        """
        for layer in CONFIG_LAYERS:
            if key in self._layers[layer]:
                return ConfigValue(self._layers[layer][key], layer)
        return ConfigValue(default, "default")

    def get_value(self, key: str, default: Any = None) -> Any:
        """Get configuration value without source tracking.

        Args:
            key: Configuration key (dotted notation)
            default: Default value if not found

        Returns:
            Configuration value
        """
        return self.get(key, default).value

    def explain(self, key: str) -> dict[str, Any]:
        """Show value from each layer for debugging.

        Args:
            key: Configuration key (dotted notation)

        Returns:
            Dict mapping layer name to value (None if not set in that layer)
        """
        return {
            layer: self._layers[layer].get(key) for layer in CONFIG_LAYERS
        }

    def list_all(self) -> dict[str, ConfigValue]:
        """List all configuration keys and their effective values.

        Returns:
            Dict mapping keys to ConfigValue (value + source)
        """
        # Collect all keys from all layers
        all_keys = set()
        for layer_dict in self._layers.values():
            all_keys.update(layer_dict.keys())

        return {key: self.get(key) for key in sorted(all_keys)}


# Global config instance
_config: LayeredConfig | None = None


def get_config() -> LayeredConfig:
    """Get global configuration instance (lazy init)."""
    global _config
    if _config is None:
        _config = LayeredConfig()
    return _config


def reset_config() -> None:
    """Reset global config (for test isolation)."""
    global _config
    _config = None
