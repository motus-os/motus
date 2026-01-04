# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""
Motus Config Schema.

Defines the dataclass model for ~/.motus/config.json settings.
"""

from dataclasses import asdict, dataclass
from typing import Any, Dict

# Fields that should NEVER be written to config.json
# These are read from environment variables only
SENSITIVE_FIELDS = frozenset({
    "anthropic_api_key",
    "openai_api_key",
    "github_token",
})


@dataclass
class MCConfigSchema:
    """Configuration schema for Motus.

    This represents the structure of ~/.motus/config.json.
    """

    version: str = "1.0"

    # Protocol
    motus_enabled: bool = True
    protocol_enforcement: str = "advisory"  # strict, advisory, off

    # Reporting
    reporting_level: str = "minimal"  # minimal, standard, verbose
    reporting_include_evidence: bool = False

    # Performance
    metrics_enabled: bool = True
    sqlite_wal_mode: bool = True
    gate_timeout_seconds: int = 300

    # Database
    use_sqlite: bool = True
    db_path: str = "~/.motus/coordination.db"
    context_cache_db_path: str = "~/.motus/context_cache.db"

    # Integrations (optional)
    anthropic_api_key: str | None = None
    openai_api_key: str | None = None
    github_token: str | None = None

    # Evidence directory (for test artifacts, etc.)
    evidence_dir: str | None = None

    def to_dict(self, include_sensitive: bool = False) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization.

        Args:
            include_sensitive: If False (default), excludes API keys and tokens.
                              These should only come from environment variables.
        """
        result = asdict(self)
        if not include_sensitive:
            for field in SENSITIVE_FIELDS:
                result.pop(field, None)
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MCConfigSchema":
        """Create from dictionary loaded from JSON."""
        # Filter out unknown keys for forward compatibility
        known_fields = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore
        filtered_data = {k: v for k, v in data.items() if k in known_fields}
        return cls(**filtered_data)
