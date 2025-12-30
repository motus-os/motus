from __future__ import annotations

from motus import messages


def test_session_not_found_formats() -> None:
    assert messages.session_not_found("abc123") == (
        "Session 'abc123' not found. Run 'mc list' to see available sessions."
    )


def test_watching_formats() -> None:
    assert messages.watching("xyz") == "Watching session 'xyz'..."


def test_error_response_includes_extras() -> None:
    payload = messages.error_response("E1", "Something broke", hint="try again")
    assert payload == {"error": "E1", "message": "Something broke", "hint": "try again"}


def test_mcp_module_main_invokes_run_server(monkeypatch) -> None:
    from motus.mcp import __main__ as mcp_main

    called = {"ok": False}

    def fake_run_server() -> None:
        called["ok"] = True

    monkeypatch.setattr(mcp_main, "run_server", fake_run_server)
    mcp_main.main()
    assert called["ok"] is True
