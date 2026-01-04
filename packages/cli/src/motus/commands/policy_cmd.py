# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Compatibility shim for policy command exports."""

import sys

from .policy_cmd_handlers import (
    _main,
    policy_plan_command,
    policy_prune_command,
    policy_run_command,
    policy_verify_command,
)

__all__ = [
    "policy_plan_command",
    "policy_prune_command",
    "policy_run_command",
    "policy_verify_command",
]

if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
