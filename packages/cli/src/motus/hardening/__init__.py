# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Hardening utilities for production resilience.

Includes:
- Circuit breakers (graceful degradation)
- Resource quotas (runaway protection)
- Idempotency keys (safe retries)
- Health checks (diagnostics)
"""

from .circuit_breaker import CircuitBreaker, CircuitOpenError
from .health import HealthChecker, HealthStatus
from .idempotency import IdempotencyManager, IdempotencyState
from .quotas import QuotaExceededError, QuotaManager

__all__ = [
    "CircuitBreaker",
    "CircuitOpenError",
    "HealthChecker",
    "HealthStatus",
    "IdempotencyManager",
    "IdempotencyState",
    "QuotaExceededError",
    "QuotaManager",
]

