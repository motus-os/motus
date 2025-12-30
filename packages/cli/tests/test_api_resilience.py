from __future__ import annotations

import time

import httpx
import pytest

from motus.api import resilience


def _make_request() -> httpx.Request:
    return httpx.Request("POST", "https://example.test/v1/chat/completions")


def _http_error(
    status_code: int, *, headers: dict[str, str] | None = None
) -> httpx.HTTPStatusError:
    request = _make_request()
    response = httpx.Response(status_code, headers=headers or {}, request=request)
    return httpx.HTTPStatusError("boom", request=request, response=response)


def test_handle_rate_limit_headers_tracks_remaining_and_reset() -> None:
    resilience.RATE_LIMIT_STATE.clear()
    resilience.handle_rate_limit_headers(
        "openrouter",
        {
            "x-ratelimit-remaining": "7",
            "x-ratelimit-reset": "1",  # seconds from now (heuristic branch)
        },
    )
    state = resilience.RATE_LIMIT_STATE["openrouter"]
    assert state.remaining == 7
    assert state.reset_at > 0.0


def test_should_preemptive_throttle_waits_until_reset(monkeypatch: pytest.MonkeyPatch) -> None:
    resilience.RATE_LIMIT_STATE.clear()
    resilience.RATE_LIMIT_STATE["openrouter"] = resilience.RateLimitState(
        remaining=0,
        reset_at=123.5,
    )
    monkeypatch.setattr(resilience.time, "time", lambda: 123.0)
    should_wait, wait_seconds = resilience.should_preemptive_throttle(
        "openrouter", remaining_threshold=1
    )
    assert should_wait is True
    assert wait_seconds == pytest.approx(0.5)


def test_call_with_backoff_retries_on_429_respects_retry_after(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    resilience.RATE_LIMIT_STATE.clear()

    sleeps: list[float] = []
    monkeypatch.setattr(resilience.time, "sleep", lambda s: sleeps.append(float(s)))

    calls: list[int] = []

    def fn() -> httpx.Response:
        calls.append(1)
        if len(calls) == 1:
            raise _http_error(429, headers={"retry-after": "0.02"})
        return httpx.Response(200, request=_make_request())

    out = resilience.call_with_backoff(
        fn,
        provider="openrouter",
        what="unit",
        max_retries=3,
        rate_limit_base_delay_seconds=0.01,
    )
    assert isinstance(out, httpx.Response)
    assert out.status_code == 200
    assert len(calls) == 2
    # Delay is max(base, retry-after).
    assert sleeps and sleeps[0] == pytest.approx(0.02)
    assert resilience.RATE_LIMIT_STATE["openrouter"].consecutive_429s == 1


def test_call_with_backoff_retries_on_request_error(monkeypatch: pytest.MonkeyPatch) -> None:
    sleeps: list[float] = []
    monkeypatch.setattr(resilience.time, "sleep", lambda s: sleeps.append(float(s)))

    calls = 0

    def fn() -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise httpx.RequestError("nope", request=_make_request())
        return httpx.Response(200, request=_make_request())

    out = resilience.call_with_backoff(
        fn,
        provider="openrouter",
        what="unit",
        max_retries=2,
        transient_base_delay_seconds=0.01,
    )
    assert out.status_code == 200
    assert calls == 2
    assert sleeps and sleeps[0] == pytest.approx(0.01)


def test_call_with_backoff_parses_http_date_retry_after(monkeypatch: pytest.MonkeyPatch) -> None:
    sleeps: list[float] = []
    monkeypatch.setattr(resilience.time, "sleep", lambda s: sleeps.append(float(s)))

    # Control time so RFC1123 parsing yields a deterministic delta.
    monkeypatch.setattr(resilience.time, "time", lambda: 1000.0)
    future = time.gmtime(1010.0)
    retry_after = time.strftime("%a, %d %b %Y %H:%M:%S GMT", future)

    calls = 0

    def fn() -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise _http_error(503, headers={"retry-after": retry_after})
        return httpx.Response(200, request=_make_request())

    out = resilience.call_with_backoff(
        fn,
        provider="openrouter",
        what="unit",
        max_retries=2,
        transient_base_delay_seconds=0.01,
        retryable_status_codes={503},
    )
    assert out.status_code == 200
    assert calls == 2
    # The parsed delta should be ~10 seconds (max(base, retry-after)).
    assert sleeps and sleeps[0] == pytest.approx(10.0)


@pytest.mark.parametrize(
    "headers, expect_exit",
    [
        ({"x-ratelimit-remaining": "abc"}, False),
        ({"x-ratelimit-reset": "abc"}, False),
    ],
)
def test_header_parsing_is_best_effort(headers: dict[str, str], expect_exit: bool) -> None:
    resilience.RATE_LIMIT_STATE.clear()
    resilience.handle_rate_limit_headers("openrouter", headers)
    assert ("openrouter" in resilience.RATE_LIMIT_STATE) is True
    assert expect_exit is False
