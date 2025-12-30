"""
Deterministic DOM smoke tests for the web dashboard.

These tests validate the presence of core UI panels and key accessibility
elements using a mock orchestrator (no live sessions or IO). This replaces
the prior skipped smoke by keeping everything in-process and deterministic.
"""

from unittest.mock import patch

from fastapi.testclient import TestClient

from motus.ui.web import MCWebServer
from tests.fixtures.mock_sessions import MockOrchestrator


def _build_client() -> TestClient:
    # Patch orchestrator to avoid hitting real session directories
    with patch("motus.ui.web.get_orchestrator", return_value=MockOrchestrator()):
        app = MCWebServer().create_app()
        return TestClient(app)


def test_dashboard_core_structure():
    client = _build_client()
    resp = client.get("/")
    assert resp.status_code == 200
    html = resp.text

    # Core panels
    assert 'id="sessions-panel"' in html
    assert 'id="feed-panel"' in html
    assert 'id="context-panel"' in html

    # Health ring + connection status
    assert 'id="health-ring"' in html
    assert 'id="health-ring-text"' in html

    # Shortcuts modal and trigger
    assert 'id="shortcuts-overlay"' in html
    assert "toggleShortcutsHelp()" in html

    # Theme toggle present (icon span inside toggle button)
    assert 'id="theme-icon"' in html


def test_dashboard_accessibility_markers():
    client = _build_client()
    resp = client.get("/")
    assert resp.status_code == 200
    html = resp.text

    # Accessibility markers: filter input placeholder, shortcuts modal dialog
    assert "Filter events by content" in html
    assert 'aria-label="Show keyboard shortcuts"' in html
    assert 'role="dialog"' in html  # shortcuts modal
