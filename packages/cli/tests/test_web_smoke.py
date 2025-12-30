"""Web UI smoke test using httpx with the running mc web server.

This is a lightweight DOM-level check to ensure key elements are present
in the dashboard when served with mock data. It does not rely on snapshots
and is intended to be fast and deterministic.

To run:
    1) Start the web server (e.g., `mc web` in another terminal)
    2) Run this test: `pytest tests/test_web_smoke.py`

Note: This uses httpx to fetch the page and BeautifulSoup to parse it.
      It requires the server to be running on 127.0.0.1:4000.
"""

import os
import time

import httpx
import pytest
from bs4 import BeautifulSoup


@pytest.fixture(scope="module")
def dashboard_html():
    """Fetch the dashboard HTML from a running mc web server.

    Assumes the server is running at http://127.0.0.1:4000.
    """
    url = os.environ.get("MC_WEB_URL", "http://127.0.0.1:4000")
    # Retry briefly in case server is just starting
    last_exc = None
    for _ in range(5):
        try:
            resp = httpx.get(url, timeout=5)
            resp.raise_for_status()
            return resp.text
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            time.sleep(0.5)
    pytest.skip(f"Web server not running at {url}: {last_exc}")


def test_dashboard_structure(dashboard_html):
    """Verify key UI elements are present in the dashboard."""
    soup = BeautifulSoup(dashboard_html, "html.parser")

    # Check for core UI elements
    assert soup.select_one(".local-only-badge") is not None, "Local badge missing"
    assert soup.select_one("#version-badge") is not None, "Version badge missing"
    assert soup.select_one(".shortcuts-overlay") is not None, "Shortcuts modal missing"
    assert soup.select_one(".health-ring") is not None, "Health ring missing"

    # Three-panel layout
    sessions_panel = soup.select_one("#sessions-panel")
    assert sessions_panel is not None, "Sessions panel missing"

    feed_panel = soup.select_one("#feed-panel")
    assert feed_panel is not None, "Feed panel missing"

    context_panel = soup.select_one("#context-panel")
    assert context_panel is not None, "Context panel missing"

    # Keyboard shortcuts modal content
    shortcuts = soup.find(string=lambda s: s and "Keyboard Shortcuts" in s)
    assert shortcuts is not None, "Shortcuts help not found"
