# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""DNA Configuration System for Motus.

DEPRECATED: Use motus.capabilities instead.

This module is a backwards-compatibility shim. New code should use:

    from motus.capabilities import Capabilities

The DNA alias is provided for existing code but will be removed in v0.3.0.

Usage (deprecated):
    from motus.dna import DNA
    dna = DNA.load("emmaus")

Usage (preferred):
    from motus.capabilities import Capabilities
    caps = Capabilities.load("emmaus")
"""

import warnings

# Import from new location
from motus.capabilities import Capabilities, deep_merge, get_nested

# Backwards compatibility alias
DNA = Capabilities

__all__ = ["DNA", "get_nested", "deep_merge"]

# Emit deprecation warning on import (only once per session)
warnings.warn(
    "motus.dna is deprecated. Use motus.capabilities instead.",
    DeprecationWarning,
    stacklevel=2,
)
