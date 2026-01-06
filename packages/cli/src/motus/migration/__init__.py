# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Path migration helpers for Motus."""

from .path_migration import (  # noqa: F401
    CANONICAL_DIRNAME,
    LEGACY_DIRNAME,
    WorkspaceResolution,
    check_legacy_path,
    find_legacy_workspace_dir,
    find_workspace_dir,
    legacy_workspace_warning,
    resolve_state_dir,
    resolve_workspace_dir,
)
