# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""
Motus Configuration Module.

Centralized configuration for all Motus components.
All magic numbers and hardcoded values should live here.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List


@dataclass(frozen=True)
class PathConfig:
    """File system paths used by Motus."""

    # Claude Code paths
    claude_dir: Path = field(default_factory=lambda: Path.home() / ".claude")

    @property
    def projects_dir(self) -> Path:
        """Claude Code projects directory."""
        return self.claude_dir / "projects"

    # Motus state directory
    state_dir: Path = field(default_factory=lambda: Path.home() / ".mc")

    @property
    def coordination_db_path(self) -> Path:
        """Coordination SQLite database path."""
        from motus.config_loader import load_config

        db_path = load_config().db_path
        return Path(db_path).expanduser()

    @property
    def context_cache_db_path(self) -> Path:
        """Context Cache SQLite database path."""
        from motus.config_loader import load_config

        db_path = load_config().context_cache_db_path
        return Path(db_path).expanduser()

    @property
    def vault_dir(self) -> Path | None:
        """Vault root directory for Vault OS policy artifacts.

        Configure via `MC_VAULT_DIR`. This is intentionally read at access time
        so tests/CLIs can set the env var without requiring re-imports.
        """

        value = os.environ.get("MC_VAULT_DIR", "").strip()
        if not value:
            return None
        return Path(value).expanduser()

    @property
    def archive_dir(self) -> Path:
        """Archive directory for cleaned up sessions."""
        return self.state_dir / "archive"

    @property
    def logs_dir(self) -> Path:
        """Logs directory."""
        return self.state_dir / "logs"

    @property
    def traces_dir(self) -> Path:
        """SDK traces directory."""
        return self.state_dir / "traces"

    def ensure_dirs(self) -> None:
        """Create all required directories."""
        self.state_dir.mkdir(exist_ok=True)
        self.archive_dir.mkdir(exist_ok=True)
        self.logs_dir.mkdir(exist_ok=True)
        self.traces_dir.mkdir(exist_ok=True)


@dataclass(frozen=True)
class SessionConfig:
    """Session discovery and management settings."""

    # Session age limits
    max_age_hours: int = 24  # Maximum age of sessions to show
    active_threshold_seconds: int = 60  # Seconds since last event to consider "active"
    idle_threshold_seconds: int = 120  # 2 minutes - threshold for crashed detection

    # Backfill limits
    max_backfill_bytes: int = 50_000  # 50KB of recent history per session
    max_backfill_events: int = 30  # Maximum events to backfill on connect

    # Display limits
    max_sessions_displayed: int = 8  # Maximum sessions in sidebar
    max_events_displayed: int = 100  # Maximum events in feed


@dataclass(frozen=True)
class WebConfig:
    """Web UI configuration."""

    # Server settings
    default_port: int = int(os.environ.get("MC_PORT", "4000"))
    host: str = os.environ.get("MC_HOST", "127.0.0.1")

    # WebSocket settings
    poll_interval_ms: int = 500  # How often to poll for new events
    reconnect_max_attempts: int = 10
    reconnect_base_delay_ms: int = 1000
    io_timeout_seconds: int = int(
        os.environ.get("MC_WS_IO_TIMEOUT", "10")
    )  # Timeout for blocking I/O work
    session_timeout_seconds: int = int(
        os.environ.get("MC_WS_SESSION_TIMEOUT", "1800")
    )  # WebSocket lifetime cap (0 disables)

    # Auto-open browser
    auto_open_browser: bool = os.environ.get("MC_NO_BROWSER", "").lower() != "true"


@dataclass(frozen=True)
class TUIConfig:
    """Terminal UI configuration."""

    # Refresh intervals
    feed_refresh_interval: float = 1.0  # Seconds between feed updates
    sessions_refresh_interval: float = 5.0  # Seconds between session list refresh
    watch_max_seconds: int = int(
        os.environ.get("MC_WATCH_MAX_SECONDS", "3600")
    )  # Watch duration cap (0 disables)

    # Display settings
    max_activity_blocks: int = 50  # Maximum activity blocks to keep in memory


@dataclass(frozen=True)
class RiskConfig:
    """Risk assessment configuration.

    Note: RISK_LEVELS is defined in commands.models as the single source of truth.
    This class exists for future risk-related configuration that doesn't belong in models.
    """

    # High-risk bash patterns
    destructive_patterns: List[str] = field(
        default_factory=lambda: [
            "rm ",
            "rm -",
            "rmdir",
            "delete",
            "drop ",
            "truncate",
            "git reset --hard",
            "git clean",
            "force push",
            "--force",
            "sudo",
            "chmod 777",
            "> /dev/",
            "mkfs",
            "dd if=",
        ]
    )

    # Sensitive file patterns
    sensitive_patterns: List[str] = field(
        default_factory=lambda: [
            ".env",
            "credentials",
            "secret",
            "password",
            "token",
            "private_key",
            "id_rsa",
            ".pem",
            "api_key",
        ]
    )


@dataclass(frozen=True)
class HealthConfig:
    """Health monitoring configuration."""

    # Health calculation weights
    friction_weight: float = 0.20  # Weight of friction in health score
    progress_weight: float = 0.50  # Weight of progress in health score
    velocity_weight: float = 0.30  # Weight of velocity in health score

    # Thresholds
    healthy_threshold: int = 75  # Score above this is "healthy"
    struggling_threshold: int = 50  # Score below this is "struggling"


@dataclass(frozen=True)
class RetentionConfig:
    """Configuration for session retention and cleanup."""

    max_session_age_days: int = 30  # Maximum age of sessions to retain
    max_session_size_mb: int = 100  # Maximum total size of session storage
    auto_prune: bool = False  # Opt-in automatic pruning


@dataclass(frozen=True)
class GovernanceStorageConfig:
    """Configuration for governance storage backend."""

    type: str = "sqlite"  # sqlite | postgres | s3
    path: str = "~/.motus/governance.db"


@dataclass(frozen=True)
class GovernanceSigningConfig:
    """Configuration for cryptographic signing."""

    enabled: bool = False
    key_path: str = "~/.motus/governance.key"


@dataclass(frozen=True)
class GovernanceConfig:
    """Configuration for the Enterprise Governance Layer."""

    enabled: bool = False
    work_receipts: bool = True
    evidence_bundles: bool = True
    contribution_ledger: bool = True
    storage: GovernanceStorageConfig = field(default_factory=GovernanceStorageConfig)
    signing: GovernanceSigningConfig = field(default_factory=GovernanceSigningConfig)


@dataclass
class MCConfig:
    """Master configuration for Motus."""

    paths: PathConfig = field(default_factory=PathConfig)
    sessions: SessionConfig = field(default_factory=SessionConfig)
    web: WebConfig = field(default_factory=WebConfig)
    tui: TUIConfig = field(default_factory=TUIConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)
    health: HealthConfig = field(default_factory=HealthConfig)
    retention: RetentionConfig = field(default_factory=RetentionConfig)
    governance: GovernanceConfig = field(default_factory=GovernanceConfig)

    def __post_init__(self) -> None:
        """Initialize directories after config creation."""
        self.paths.ensure_dirs()


# Global config instance - use this throughout the application
config = MCConfig()


# Convenience exports
CLAUDE_DIR = config.paths.claude_dir
PROJECTS_DIR = config.paths.projects_dir
MC_STATE_DIR = config.paths.state_dir
ARCHIVE_DIR = config.paths.archive_dir

# Note: RISK_LEVELS, DESTRUCTIVE_PATTERNS, SENSITIVE_PATTERNS are
# canonical in commands.models - import from there to avoid duplication
