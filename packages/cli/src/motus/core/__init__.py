# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Core infrastructure for Motus.

This module provides foundational components:
- Database management with SQLite
- Migration runner for schema evolution
- Layered configuration (CLI > env > project > user > system)
- Runtime context for dependency injection
- Error handling and standardized exceptions
- Bootstrap logic for first-run setup
"""

from .bootstrap import (
    bootstrap_database,
    ensure_database,
    get_instance_id,
    get_instance_name,
    is_first_run,
    set_instance_name,
)
from .claims import DeployStatus, can_deploy
from .context import RuntimeContext, get_context, reset_context, set_context
from .database import (
    EXPECTED_SCHEMA_VERSION,
    DatabaseManager,
    configure_connection,
    get_database_path,
    get_db_manager,
    get_readonly_connection,
    reset_db_manager,
    verify_schema_version,
)
from .errors import (
    ConfigError,
    DatabaseError,
    DiskFullError,
    MigrationError,
    MotusError,
    SchemaError,
    is_disk_error,
)
from .layered_config import ConfigValue, LayeredConfig, get_config, reset_config
from .migrations import Migration, MigrationRunner
from .roadmap import (
    RoadmapAPI,
    RoadmapError,
    RoadmapItem,
    RoadmapResponse,
    claim,
    complete,
    my_work,
    ready,
    release,
    status,
)

__all__ = [
    # Errors
    "ConfigError",
    "DatabaseError",
    "DiskFullError",
    "MigrationError",
    "MotusError",
    "SchemaError",
    "is_disk_error",
    # Database
    "DatabaseManager",
    "EXPECTED_SCHEMA_VERSION",
    "configure_connection",
    "get_database_path",
    "get_db_manager",
    "get_readonly_connection",
    "reset_db_manager",
    "verify_schema_version",
    # Migrations
    "Migration",
    "MigrationRunner",
    # Config
    "ConfigValue",
    "LayeredConfig",
    "get_config",
    "reset_config",
    # Context
    "RuntimeContext",
    "get_context",
    "reset_context",
    "set_context",
    # Bootstrap
    "bootstrap_database",
    "ensure_database",
    "get_instance_id",
    "get_instance_name",
    "is_first_run",
    "set_instance_name",
    # Claims
    "DeployStatus",
    "can_deploy",
    # Roadmap
    "RoadmapAPI",
    "RoadmapError",
    "RoadmapItem",
    "RoadmapResponse",
    "claim",
    "complete",
    "my_work",
    "ready",
    "release",
    "status",
]
