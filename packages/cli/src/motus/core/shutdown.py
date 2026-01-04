# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Graceful shutdown helpers.

Provides a minimal signal-aware shutdown manager that can:
- register cleanup callbacks
- run callbacks on SIGINT/SIGTERM
"""

from __future__ import annotations

import signal
from dataclasses import dataclass
from typing import Callable, List, Optional


@dataclass(frozen=True)
class ShutdownHook:
    name: str
    callback: Callable[[], None]


class ShutdownManager:
    def __init__(self) -> None:
        self._hooks: List[ShutdownHook] = []
        self._installed = False
        self._has_shutdown = False

    def register(self, name: str, callback: Callable[[], None]) -> None:
        self._hooks.append(ShutdownHook(name=name, callback=callback))

    def shutdown(self, *, reason: str) -> None:
        if self._has_shutdown:
            return
        self._has_shutdown = True
        for hook in self._hooks:
            try:
                hook.callback()
            except Exception:
                # Best-effort cleanup; do not raise from shutdown path.
                continue

    def install_signal_handlers(self) -> None:
        if self._installed:
            return
        self._installed = True

        def _handler(signum: int, _frame: Optional[object]) -> None:
            self.shutdown(reason=f"signal:{signum}")
            raise SystemExit(128 + signum)

        for sig in (getattr(signal, "SIGINT", None), getattr(signal, "SIGTERM", None)):
            if sig is None:
                continue
            try:
                signal.signal(sig, _handler)
            except Exception:
                continue

