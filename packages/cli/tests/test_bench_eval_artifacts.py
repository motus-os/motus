from __future__ import annotations

import json
from pathlib import Path

from motus.bench.eval_artifacts import (
    EventChainWriter,
    sha256_hex_bytes,
    sha256_hex_file,
    sha256_hex_text,
    sha256_ref,
    verify_event_chain,
    write_json,
)


def test_sha256_helpers(tmp_path: Path) -> None:
    assert sha256_ref("abc") == "sha256:abc"
    assert sha256_hex_text("hi") == sha256_hex_bytes(b"hi")

    path = tmp_path / "x.txt"
    path.write_text("hello\n", encoding="utf-8")
    assert sha256_hex_file(path) == sha256_hex_text("hello\n")


def test_write_json_is_parseable_and_newline_terminated(tmp_path: Path) -> None:
    path = tmp_path / "payload.json"
    payload = {"a": 1, "b": 2}
    write_json(path, payload)
    raw = path.read_text(encoding="utf-8")
    assert raw.endswith("\n")
    assert json.loads(raw) == payload


def test_event_chain_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    writer = EventChainWriter(path)

    writer.append(ts="2025-01-01T00:00:00Z", event_type="start")
    writer.append(ts="2025-01-01T00:00:01Z", event_type="step", payload={"n": 1})
    writer.append(ts="2025-01-01T00:00:02Z", event_type="done")

    result = verify_event_chain(path)
    assert result.ok is True
    assert result.head_hash == writer.head_hash


def test_event_chain_detects_tampering(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    writer = EventChainWriter(path)
    writer.append(ts="2025-01-01T00:00:00Z", event_type="start")
    writer.append(ts="2025-01-01T00:00:01Z", event_type="done")

    lines = path.read_text(encoding="utf-8").splitlines()
    record = json.loads(lines[1])
    record["prev_hash"] = "0" * 64  # wrong
    lines[1] = json.dumps(record, sort_keys=True, separators=(",", ":"))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    result = verify_event_chain(path)
    assert result.ok is False
    assert "prev_hash mismatch" in (result.error or "")
