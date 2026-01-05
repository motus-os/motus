# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""Contract tests for web UI behavior."""

from __future__ import annotations

def test_websocket_history_timeout_returns_error(monkeypatch):
    """Web UI should return an error instead of hanging on history timeouts."""
    from fastapi.testclient import TestClient

    from motus.ui.web import MCWebServer
    from motus.ui.web.websocket_handler import WebSocketHandler

    async def _fake_run_blocking(self, func, *args, timeout, default, context, **kwargs):
        return default

    monkeypatch.setattr(WebSocketHandler, "_run_blocking", _fake_run_blocking)

    server = MCWebServer(port=0)
    app = server.create_app()
    client = TestClient(app)

    with client.websocket_connect("/ws") as websocket:
        # initial handshake messages
        websocket.receive_json()  # connected
        websocket.receive_json()  # sessions

        websocket.send_json({"type": "select_session", "session_id": "demo-session"})
        response = websocket.receive_json()

        assert response["type"] == "error"
        assert "timed out" in response["message"].lower()
