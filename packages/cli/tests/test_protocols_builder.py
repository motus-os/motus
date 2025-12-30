from __future__ import annotations

import inspect
from typing import Protocol

from motus.protocols_builder import SessionBuilder


def test_session_builder_is_protocol() -> None:
    assert issubclass(SessionBuilder, Protocol)


def test_session_builder_source_name_is_property() -> None:
    assert isinstance(SessionBuilder.source_name, property)


def test_session_builder_discover_signature() -> None:
    signature = inspect.signature(SessionBuilder.discover)
    params = list(signature.parameters.values())
    assert params[1].name == "max_age_hours"
    assert params[1].default == 24


def test_session_builder_parse_events_signature() -> None:
    signature = inspect.signature(SessionBuilder.parse_events)
    params = list(signature.parameters.values())
    assert params[1].name == "file_path"


def test_session_builder_extract_thinking_signature() -> None:
    signature = inspect.signature(SessionBuilder.extract_thinking)
    params = list(signature.parameters.values())
    assert params[1].name == "file_path"


def test_session_builder_extract_decisions_signature() -> None:
    signature = inspect.signature(SessionBuilder.extract_decisions)
    params = list(signature.parameters.values())
    assert params[1].name == "file_path"


def test_session_builder_get_last_action_signature() -> None:
    signature = inspect.signature(SessionBuilder.get_last_action)
    params = list(signature.parameters.values())
    assert params[1].name == "file_path"


def test_session_builder_has_completion_marker_signature() -> None:
    signature = inspect.signature(SessionBuilder.has_completion_marker)
    params = list(signature.parameters.values())
    assert params[1].name == "file_path"


def test_session_builder_protocol_methods_return_ellipsis() -> None:
    assert SessionBuilder.source_name.fget(None) in {None, Ellipsis}
    assert SessionBuilder.discover(None) in {None, Ellipsis}
    assert SessionBuilder.parse_events(None, None) in {None, Ellipsis}
    assert SessionBuilder.extract_thinking(None, None) in {None, Ellipsis}
    assert SessionBuilder.extract_decisions(None, None) in {None, Ellipsis}
    assert SessionBuilder.get_last_action(None, None) in {None, Ellipsis}
    assert SessionBuilder.has_completion_marker(None, None) in {None, Ellipsis}
