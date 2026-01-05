# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""
Motus Logging Module.

Structured logging for all Motus components.
"""

import json
import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from collections import OrderedDict
from datetime import datetime
from typing import Any

from .config import config


class MCFormatter(logging.Formatter):
    """Custom formatter that outputs JSON for file logs and pretty text for console."""

    def __init__(self, json_format: bool = False):
        super().__init__()
        self.json_format = json_format

    def format(self, record: logging.LogRecord) -> str:
        if self.json_format:
            log_data = {
                "timestamp": datetime.utcnow().isoformat(),
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
            }
            # Add extra fields if present
            if hasattr(record, "session_id"):
                log_data["session_id"] = record.session_id
            if hasattr(record, "tool_name"):
                log_data["tool_name"] = record.tool_name
            if hasattr(record, "event_type"):
                log_data["event_type"] = record.event_type
            if record.exc_info:
                log_data["exception"] = self.formatException(record.exc_info)
            return json.dumps(log_data)
        else:
            # Pretty console format
            level_colors = {
                "DEBUG": "\033[36m",  # Cyan
                "INFO": "\033[32m",  # Green
                "WARNING": "\033[33m",  # Yellow
                "ERROR": "\033[31m",  # Red
                "CRITICAL": "\033[35m",  # Magenta
            }
            reset = "\033[0m"
            color = level_colors.get(record.levelname, "")

            timestamp = datetime.now().strftime("%H:%M:%S")
            msg = f"{color}[{timestamp}] {record.levelname:8}{reset} {record.name}: {record.getMessage()}"

            if record.exc_info:
                msg += f"\n{self.formatException(record.exc_info)}"
            return msg


class MCLogger:
    """
    Structured logger for Motus.

    Usage:
        from motus.logging import get_logger
        logger = get_logger(__name__)

        logger.info("Processing session", session_id="abc123")
        logger.error("Failed to parse", exc_info=True, tool_name="Bash")
    """

    def __init__(self, name: str, level: int = logging.INFO):
        self.logger = logging.getLogger(f"motus.{name}")
        self.logger.setLevel(level)

        # Avoid duplicate handlers
        if not self.logger.handlers:
            # Console handler - pretty format
            console_handler = logging.StreamHandler(sys.stderr)
            console_handler.setLevel(logging.WARNING)  # Only warnings+ to console
            console_handler.setFormatter(MCFormatter(json_format=False))
            self.logger.addHandler(console_handler)

            # File handler - JSON format
            log_file = config.paths.logs_dir / "motus.log"
            try:
                file_handler = RotatingFileHandler(
                    log_file,
                    maxBytes=10 * 1024 * 1024,
                    backupCount=5,
                )
                file_handler.setLevel(logging.DEBUG)
                file_handler.setFormatter(MCFormatter(json_format=True))
                self.logger.addHandler(file_handler)
            except (OSError, PermissionError):
                # Can't write to log file, continue without it
                pass

    def _log(self, level: int, msg: str, **kwargs: Any) -> None:
        """Internal log method that handles extra fields."""
        extra_fields = {}
        exc_info = kwargs.pop("exc_info", None)

        for key, value in kwargs.items():
            extra_fields[key] = value

        # Create a LogRecord with extra fields
        record = self.logger.makeRecord(
            self.logger.name,
            level,
            "(unknown)",
            0,
            msg,
            (),
            exc_info,
        )
        for key, value in extra_fields.items():
            setattr(record, key, value)

        self.logger.handle(record)

    def debug(self, msg: str, **kwargs: Any) -> None:
        """Log debug message."""
        self._log(logging.DEBUG, msg, **kwargs)

    def info(self, msg: str, **kwargs: Any) -> None:
        """Log info message."""
        self._log(logging.INFO, msg, **kwargs)

    def warning(self, msg: str, **kwargs: Any) -> None:
        """Log warning message."""
        self._log(logging.WARNING, msg, **kwargs)

    def error(self, msg: str, **kwargs: Any) -> None:
        """Log error message."""
        self._log(logging.ERROR, msg, **kwargs)

    def critical(self, msg: str, **kwargs: Any) -> None:
        """Log critical message."""
        self._log(logging.CRITICAL, msg, **kwargs)

    def exception(self, msg: str, **kwargs: Any) -> None:
        """Log exception with traceback."""
        kwargs["exc_info"] = True
        self._log(logging.ERROR, msg, **kwargs)


LOGGER_CACHE_MAX = max(1, int(os.environ.get("MC_LOGGER_CACHE_MAX", "512")))

# Logger cache (LRU)
_loggers: "OrderedDict[str, MCLogger]" = OrderedDict()


def get_logger(name: str) -> MCLogger:
    """
    Get or create a logger for the given name.

    Args:
        name: Logger name (typically __name__)

    Returns:
        MCLogger instance
    """
    if name in _loggers:
        logger = _loggers.pop(name)
        _loggers[name] = logger
        return logger

    logger = MCLogger(name)
    _loggers[name] = logger
    if len(_loggers) > LOGGER_CACHE_MAX:
        _, evicted = _loggers.popitem(last=False)
        for handler in list(evicted.logger.handlers):
            try:
                handler.close()
            except Exception:
                pass
            evicted.logger.removeHandler(handler)
    return logger


def set_log_level(level: int) -> None:
    """Set log level for all Motus loggers."""
    for logger in _loggers.values():
        logger.logger.setLevel(level)


def enable_debug() -> None:
    """Enable debug logging to console."""
    for logger in _loggers.values():
        for handler in logger.logger.handlers:
            if isinstance(handler, logging.StreamHandler):
                handler.setLevel(logging.DEBUG)
