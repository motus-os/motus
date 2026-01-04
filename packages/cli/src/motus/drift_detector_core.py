# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Core drift detection logic."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from .drift_detector_patterns import (
    DriftSignal,
    DriftState,
    UserIntent,
    check_directory_drift,
    check_file_type_drift,
    check_tool_pattern_drift,
    extract_intent,
)
from .exceptions import DriftError, InvalidIntentError, InvalidSessionError
from .logging import get_logger

logger = get_logger(__name__)


class DriftDetector:
    """
    Detects drift between user intent and agent actions.

    Usage:
        detector = DriftDetector()
        detector.set_intent("Help me write a blog post about AI governance")

        # On each agent action:
        drift = detector.check_action(tool_name="Edit", file_path="/code/app.py")
        if drift.is_drifting:
            # Surface in UI health indicator
    """

    def __init__(self):
        self._intents: Dict[str, UserIntent] = {}
        self._states: Dict[str, DriftState] = {}
        self._action_history: Dict[str, List[dict]] = {}

    @staticmethod
    def _require_non_empty_str(value: object, *, field_name: str) -> str:
        if not isinstance(value, str):
            raise DriftError(
                f"Invalid {field_name}", details=f"type={type(value).__name__}"
            )
        stripped = value.strip()
        if not stripped:
            raise DriftError(f"Invalid {field_name}", details="empty")
        return stripped

    @classmethod
    def _validate_session_id(cls, session_id: object) -> str:
        try:
            return cls._require_non_empty_str(session_id, field_name="session_id")
        except DriftError as e:
            raise InvalidSessionError(e.message, details=e.details) from e

    @classmethod
    def _validate_user_message(cls, message: object) -> str:
        try:
            return cls._require_non_empty_str(message, field_name="user_message")
        except DriftError as e:
            raise InvalidIntentError(e.message, details=e.details) from e

    def set_intent(self, session_id: str, user_message: str) -> UserIntent:
        session_id = self._validate_session_id(session_id)
        user_message = self._validate_user_message(user_message)
        intent = self._extract_intent(user_message)
        self._intents[session_id] = intent

        if session_id in self._states:
            self._states[session_id] = DriftState(session_id=session_id)

        logger.debug(
            "Set intent for session",
            session_id=session_id[:8],
            dirs=str(intent.mentioned_directories),
            types=str(intent.mentioned_file_types),
            keywords=str(list(intent.keywords)[:5]),
        )
        return intent

    def check_action(
        self,
        session_id: str,
        tool_name: str,
        file_path: Optional[str] = None,
        tool_input: Optional[dict] = None,
    ) -> DriftState:
        session_id = self._validate_session_id(session_id)
        tool_name = self._require_non_empty_str(tool_name, field_name="tool_name")
        if file_path is not None and not isinstance(file_path, (str, Path)):
            raise DriftError(
                "Invalid file_path", details=f"type={type(file_path).__name__}"
            )
        if isinstance(file_path, Path):
            file_path = str(file_path)

        if session_id not in self._states:
            self._states[session_id] = DriftState(session_id=session_id)

        state = self._states[session_id]
        intent = self._intents.get(session_id)

        if not intent:
            return state

        action = {
            "tool": tool_name,
            "path": file_path,
            "input": tool_input,
            "timestamp": datetime.now(),
        }
        if session_id not in self._action_history:
            self._action_history[session_id] = []
        self._action_history[session_id].append(action)
        self._action_history[session_id] = self._action_history[session_id][-20:]

        signals = []

        if file_path:
            dir_signal = self._check_directory_drift(intent, file_path)
            if dir_signal:
                signals.append(dir_signal)

        if file_path:
            type_signal = self._check_file_type_drift(intent, file_path)
            if type_signal:
                signals.append(type_signal)

        tool_signal = self._check_tool_pattern_drift(
            intent, self._action_history[session_id]
        )
        if tool_signal:
            signals.append(tool_signal)

        for signal in signals:
            state.add_signal(signal)
            logger.info(
                "Drift detected",
                signal_type=signal.signal_type,
                description=signal.description,
            )

        return state

    def get_state(self, session_id: str) -> DriftState:
        if session_id not in self._states:
            self._states[session_id] = DriftState(session_id=session_id)
        return self._states[session_id]

    def clear_session(self, session_id: str) -> None:
        self._intents.pop(session_id, None)
        self._states.pop(session_id, None)
        self._action_history.pop(session_id, None)

    def _extract_intent(self, message: str) -> UserIntent:
        message = self._validate_user_message(message)
        return extract_intent(message)

    def _check_directory_drift(
        self, intent: UserIntent, file_path: str
    ) -> Optional[DriftSignal]:
        return check_directory_drift(intent, file_path)

    def _check_file_type_drift(
        self, intent: UserIntent, file_path: str
    ) -> Optional[DriftSignal]:
        return check_file_type_drift(intent, file_path)

    def _check_tool_pattern_drift(
        self, intent: UserIntent, recent_actions: List[dict]
    ) -> Optional[DriftSignal]:
        return check_tool_pattern_drift(intent, recent_actions)
