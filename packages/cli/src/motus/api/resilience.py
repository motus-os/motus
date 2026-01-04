# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Resilience utilities for external HTTP APIs (rate limits, retries, backoff)."""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import timezone
from email.utils import parsedate_to_datetime
from typing import Callable, Mapping, TypeVar

import httpx

from motus.observability.io_capture import record_network_call

T = TypeVar("T")


@dataclass
class RateLimitState:
    remaining: int = -1  # Unknown
    reset_at: float = 0.0  # epoch seconds when known
    last_429_at: float = 0.0
    consecutive_429s: int = 0


RATE_LIMIT_STATE: dict[str, RateLimitState] = {}


def _parse_int(value: str | None) -> int | None:
    if value is None:
        return None
    raw = value.strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def _parse_reset_at(value: str | None, *, now: float) -> float | None:
    if value is None:
        return None
    raw = value.strip()
    if not raw:
        return None
    try:
        parsed = float(raw)
    except ValueError:
        return None
    # Heuristic: big values are epoch seconds, small values are seconds-from-now.
    if parsed > 1_000_000_000:
        return parsed
    return now + parsed


def _parse_retry_after_seconds(value: str | None, *, now: float) -> float | None:
    if value is None:
        return None
    raw = value.strip()
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        pass
    try:
        dt = parsedate_to_datetime(raw)
    except (TypeError, ValueError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return max(0.0, dt.timestamp() - now)


def handle_rate_limit_headers(provider: str, headers: Mapping[str, str]) -> None:
    """Track rate limit state from response headers (best-effort)."""

    now = time.time()
    state = RATE_LIMIT_STATE.setdefault(provider, RateLimitState())

    remaining = _parse_int(headers.get("x-ratelimit-remaining"))
    if remaining is not None:
        state.remaining = remaining

    reset_at = _parse_reset_at(headers.get("x-ratelimit-reset"), now=now)
    if reset_at is not None:
        state.reset_at = reset_at


def should_preemptive_throttle(
    provider: str, *, remaining_threshold: int = 10
) -> tuple[bool, float]:
    """Return (should_wait, wait_seconds) based on observed rate limit state."""

    state = RATE_LIMIT_STATE.get(provider)
    if state is None or state.remaining < 0:
        return (False, 0.0)
    if state.remaining >= remaining_threshold:
        return (False, 0.0)

    now = time.time()
    wait_seconds = max(0.0, float(state.reset_at or 0.0) - now)
    if wait_seconds <= 0:
        return (False, 0.0)
    return (True, wait_seconds)


def call_with_backoff(
    fn: Callable[[], T],
    *,
    provider: str,
    what: str,
    max_retries: int = 3,
    transient_base_delay_seconds: float = 2.0,
    rate_limit_base_delay_seconds: float = 30.0,
    retryable_status_codes: set[int] | None = None,
    log: Callable[[str], None] | None = None,
) -> T:
    """Run `fn` with pre-emptive throttling and exponential backoff retries.

    - 429 backoff uses `rate_limit_base_delay_seconds` (default 30s) and respects Retry-After.
    - 5xx + request errors use `transient_base_delay_seconds` (default 2s).
    """

    if max_retries <= 0:
        raise ValueError("max_retries must be > 0")
    if transient_base_delay_seconds <= 0 or rate_limit_base_delay_seconds <= 0:
        raise ValueError("base delay seconds must be > 0")

    status_codes = retryable_status_codes or {429, 500, 502, 503, 504}
    emit = log or (lambda _: None)
    last_error: Exception | None = None

    for attempt in range(max_retries):
        should_wait, wait_seconds = should_preemptive_throttle(provider)
        if should_wait:
            emit(f"{what}: rate limit low for {provider}, waiting {wait_seconds:.1f}s")
            time.sleep(wait_seconds)

        try:
            result = fn()
            if isinstance(result, httpx.Response):
                handle_rate_limit_headers(provider, result.headers)
                try:
                    request = result.request
                    record_network_call(
                        url=str(request.url),
                        method=request.method,
                        status_code=result.status_code,
                        bytes_in=len(result.content) if result.content is not None else None,
                        bytes_out=None,
                        source=what,
                    )
                except Exception:
                    pass
            return result
        except httpx.HTTPStatusError as e:
            status = int(getattr(e.response, "status_code", 0) or 0)
            if isinstance(getattr(e, "response", None), httpx.Response):
                handle_rate_limit_headers(provider, e.response.headers)
                try:
                    request = e.response.request
                    record_network_call(
                        url=str(request.url),
                        method=request.method,
                        status_code=status,
                        bytes_in=len(e.response.content) if e.response.content is not None else None,
                        bytes_out=None,
                        source=what,
                    )
                except Exception:
                    pass

            if status not in status_codes:
                raise SystemExit(f"{what}: HTTP {status}") from e

            last_error = e
            now = time.time()
            retry_after = _parse_retry_after_seconds(e.response.headers.get("retry-after"), now=now)
            if status == 429:
                delay = rate_limit_base_delay_seconds * (2**attempt)
                if retry_after is not None:
                    delay = max(delay, retry_after)
                state = RATE_LIMIT_STATE.setdefault(provider, RateLimitState())
                state.last_429_at = now
                state.consecutive_429s += 1
                emit(
                    f"{what}: rate limited (429), waiting {delay:.1f}s (attempt {attempt + 1}/{max_retries})"
                )
                time.sleep(delay)
                continue

            delay = transient_base_delay_seconds * (2**attempt)
            if retry_after is not None:
                delay = max(delay, retry_after)
            emit(
                f"{what}: transient HTTP {status}, waiting {delay:.1f}s (attempt {attempt + 1}/{max_retries})"
            )
            time.sleep(delay)
            continue
        except httpx.RequestError as e:
            last_error = e
            try:
                request = getattr(e, "request", None)
                record_network_call(
                    url=str(request.url) if request is not None else "unknown",
                    method=getattr(request, "method", None) if request is not None else None,
                    status_code=None,
                    bytes_in=None,
                    bytes_out=None,
                    source=what,
                )
            except Exception:
                pass
            delay = transient_base_delay_seconds * (2**attempt)
            emit(
                f"{what}: request error, waiting {delay:.1f}s (attempt {attempt + 1}/{max_retries})"
            )
            time.sleep(delay)
            continue

    raise SystemExit(f"{what}: failed after {max_retries} retries: {last_error}") from last_error
