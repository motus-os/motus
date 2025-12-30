"""Tests for session identity generation."""

import hashlib
import re

from motus.session_identity import generate_session_id


def _parse_session_id(session_id: str) -> tuple[str, str, str, str, str]:
    parts = session_id.split("_")
    assert len(parts) == 5
    return parts[0], parts[1], parts[2], parts[3], parts[4]


def test_session_id_format():
    timestamp = "20251220T120000Z"
    context = b"test"
    session_id = generate_session_id(timestamp, "opus", context)
    prefix, marker, ts, agent_type, hash_part = _parse_session_id(session_id)

    assert prefix == "mot"
    assert marker == "ses"
    assert ts == timestamp
    assert agent_type == "opus"
    assert re.fullmatch(r"[0-9a-f]{8}", hash_part)
    assert hash_part == hashlib.sha256(context).hexdigest()[:8]


def test_timestamp_normalization():
    raw = "2025-12-20T12:00:00Z"
    session_id = generate_session_id(raw, "haiku", b"x")
    _, _, ts, _, _ = _parse_session_id(session_id)

    assert ts == "20251220T120000Z"


def test_session_id_deterministic():
    timestamp = "20251220T120000Z"
    context = b"repeat"
    first = generate_session_id(timestamp, "codex", context)
    second = generate_session_id(timestamp, "codex", context)

    assert first == second


def test_session_id_differs_by_context():
    timestamp = "20251220T120000Z"
    first = generate_session_id(timestamp, "codex", b"a")
    second = generate_session_id(timestamp, "codex", b"b")

    assert first != second
