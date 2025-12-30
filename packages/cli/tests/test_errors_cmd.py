from __future__ import annotations

import json
from argparse import Namespace

from motus.commands.errors_cmd import errors_command
from motus.errors.extractor import ErrorCategory, extract_errors_from_jsonl


def test_extract_errors_from_jsonl(tmp_path):
    session = tmp_path / "session.jsonl"
    session.write_text(
        "\n".join(
            [
                '{"type":"tool_result","exit_code":137,"command":"pytest"}',
                '{"type":"api_response","status_code":429,"error":"Too Many Requests"}',
                '{"type":"tool_result","exit_code":127,"command":"docker"}',
                '{"type":"tool_result","error":"ENOENT: /tmp/missing.json"}',
            ]
        )
        + "\n"
    )

    summary = extract_errors_from_jsonl(session)
    assert summary.total_errors == 4
    assert summary.by_category["exit"] == 2
    assert summary.by_category["api"] == 1
    assert summary.by_category["file_io"] == 1
    assert summary.by_exit_code == {127: 1, 137: 1}
    assert summary.by_http_status == {429: 1}
    assert summary.by_file_error == {"ENOENT": 1}

    api_only = extract_errors_from_jsonl(session, category=ErrorCategory.API)
    assert api_only.total_errors == 1
    assert api_only.by_category == {"api": 1}


def test_errors_command_json_output(tmp_path, capsys):
    session = tmp_path / "session.jsonl"
    session.write_text(
        "\n".join(
            [
                '{"type":"tool_result","exit_code":137,"command":"pytest"}',
                '{"type":"api_response","status_code":503,"error":"Service Unavailable"}',
            ]
        )
        + "\n"
    )

    args = Namespace(session=str(session), session_id=None, last=None, category=None, json=True)
    rc = errors_command(args)
    assert rc == 0

    out = capsys.readouterr().out
    payload = json.loads(out)
    assert payload["total_errors"] == 2
    assert payload["by_exit_code"] == {"137": 1} or payload["by_exit_code"] == {137: 1}
