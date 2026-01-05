from __future__ import annotations

import json
import logging
import sys
from dataclasses import dataclass

import pytest

import motus.logging as mc_logging
from tests.fixtures.constants import FIXED_TIMESTAMP, FIXED_TIMESTAMP_NAIVE


@dataclass
class _FixedDateTime:
    @staticmethod
    def utcnow():
        return FIXED_TIMESTAMP

    @staticmethod
    def now():
        return FIXED_TIMESTAMP_NAIVE


def test_mcformatter_json_includes_extra_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mc_logging, "datetime", _FixedDateTime)
    formatter = mc_logging.MCFormatter(json_format=True)
    record = logging.LogRecord(
        name="motus.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="hello",
        args=(),
        exc_info=None,
    )
    record.session_id = "s1"
    record.tool_name = "Bash"
    record.event_type = "tool"

    payload = json.loads(formatter.format(record))

    assert payload["message"] == "hello"
    assert payload["session_id"] == "s1"
    assert payload["tool_name"] == "Bash"
    assert payload["event_type"] == "tool"


def test_mcformatter_json_includes_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mc_logging, "datetime", _FixedDateTime)
    formatter = mc_logging.MCFormatter(json_format=True)

    try:
        raise ValueError("boom")
    except ValueError:
        exc_info = sys.exc_info()

    record = logging.LogRecord(
        name="motus.test",
        level=logging.ERROR,
        pathname=__file__,
        lineno=1,
        msg="failed",
        args=(),
        exc_info=exc_info,
    )

    payload = json.loads(formatter.format(record))
    assert payload["message"] == "failed"
    assert "exception" in payload


def test_mcformatter_console_includes_level_and_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(mc_logging, "datetime", _FixedDateTime)
    formatter = mc_logging.MCFormatter(json_format=False)
    record = logging.LogRecord(
        name="motus.test",
        level=logging.WARNING,
        pathname=__file__,
        lineno=1,
        msg="warn",
        args=(),
        exc_info=None,
    )

    output = formatter.format(record)
    assert "WARNING" in output
    assert "warn" in output


def test_mclogger_skips_file_handler_on_permission_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from logging.handlers import RotatingFileHandler

    # Clear logger cache to ensure fresh instance
    monkeypatch.setattr(mc_logging, "_loggers", {})

    def _raise_permission(*_args, **_kwargs):
        raise PermissionError("nope")

    # Patch RotatingFileHandler (what the code actually uses)
    monkeypatch.setattr(mc_logging, "RotatingFileHandler", _raise_permission)
    logger = mc_logging.MCLogger("perm-test")
    assert not any(
        isinstance(handler, RotatingFileHandler) for handler in logger.logger.handlers
    )


def test_get_logger_caches_instances(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mc_logging, "_loggers", {})
    first = mc_logging.get_logger("cache")
    second = mc_logging.get_logger("cache")
    assert first is second


def test_set_log_level_updates_existing_loggers(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mc_logging, "_loggers", {})
    logger = mc_logging.get_logger("level")
    mc_logging.set_log_level(logging.DEBUG)
    assert logger.logger.level == logging.DEBUG


def test_enable_debug_sets_stream_handler_level(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mc_logging, "_loggers", {})
    logger = mc_logging.get_logger("stream")
    mc_logging.enable_debug()
    stream_levels = [
        handler.level
        for handler in logger.logger.handlers
        if isinstance(handler, logging.StreamHandler)
    ]
    assert stream_levels and all(level == logging.DEBUG for level in stream_levels)


def test_mclogger_records_extra_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mc_logging, "_loggers", {})
    logger = mc_logging.get_logger("extra")

    records: list[logging.LogRecord] = []

    class _Capture(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(record)

    capture = _Capture()
    capture.setLevel(logging.INFO)
    logger.logger.addHandler(capture)

    logger.info("hello", session_id="s1")

    assert records
    assert records[0].session_id == "s1"


def test_mclogger_exception_sets_exc_info(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mc_logging, "_loggers", {})
    logger = mc_logging.get_logger("exc")
    logger.logger.propagate = False

    records: list[logging.LogRecord] = []

    class _Capture(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(record)

    logger.logger.addHandler(_Capture())

    try:
        raise RuntimeError("boom")
    except RuntimeError:
        logger.exception("failed")

    assert records
    assert records[0].exc_info is True


def test_mclogger_includes_tool_name(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mc_logging, "_loggers", {})
    logger = mc_logging.get_logger("tool")

    records: list[logging.LogRecord] = []

    class _Capture(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(record)

    logger.logger.addHandler(_Capture())
    logger.info("run", tool_name="Bash")

    assert records
    assert records[0].tool_name == "Bash"
