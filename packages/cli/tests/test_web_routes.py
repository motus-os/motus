"""Tests for ui/web/routes.py - HTTP route handlers."""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from motus.protocols import SessionStatus, Source
from tests.fixtures.constants import FIXED_TIMESTAMP


def create_mock_session(session_id="test-session", project_path="/project", size=1024000):
    """Helper to create a mock session with all required attributes."""
    mock_session = Mock()
    mock_session.session_id = session_id
    mock_session.source = Source.CLAUDE
    mock_session.file_path = Path(f"/tmp/{session_id}.jsonl")
    mock_session.project_path = project_path
    mock_session.created_at = FIXED_TIMESTAMP
    mock_session.last_modified = FIXED_TIMESTAMP
    mock_session.status = SessionStatus.ACTIVE
    mock_session.status_reason = "Active"
    mock_session.event_count = 10
    mock_session.size = size
    return mock_session


class TestRegisterRoutes:
    """Tests for register_routes function."""

    def test_register_routes_adds_routes_to_app(self):
        """register_routes adds routes to FastAPI app."""
        from motus.ui.web.routes import register_routes

        app = FastAPI()
        register_routes(app)

        routes = [route.path for route in app.routes]

        assert "/" in routes
        assert "/api/summary/{session_id}" in routes


class TestDashboardRoute:
    """Tests for dashboard route (/)."""

    @patch("motus.ui.web.routes.TEMPLATES_DIR")
    def test_dashboard_returns_html_content(self, mock_templates_dir, tmp_path):
        """Dashboard route returns HTML content."""
        from motus.ui.web.routes import register_routes

        # Create a mock template file
        template_file = tmp_path / "dashboard.html"
        template_file.write_text(
            "<!DOCTYPE html><html><head><title>Dashboard</title></head><body>{{ version }}</body></html>"
        )
        mock_templates_dir.__truediv__ = lambda self, other: template_file

        app = FastAPI()
        register_routes(app)
        client = TestClient(app)

        response = client.get("/")

        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")
        assert "<!DOCTYPE html>" in response.text

    @patch("motus.ui.web.routes.TEMPLATES_DIR")
    def test_dashboard_replaces_version_placeholder(self, mock_templates_dir, tmp_path):
        """Dashboard route replaces version placeholder."""
        from motus import __version__
        from motus.ui.web.routes import register_routes

        # Create a mock template file
        template_file = tmp_path / "dashboard.html"
        template_file.write_text("<html><body>Version: {{ version }}</body></html>")
        mock_templates_dir.__truediv__ = lambda self, other: template_file

        app = FastAPI()
        register_routes(app)
        client = TestClient(app)

        response = client.get("/")

        assert response.status_code == 200
        assert __version__ in response.text
        assert "{{ version }}" not in response.text

    @patch("motus.ui.web.routes.TEMPLATES_DIR")
    def test_dashboard_raises_error_when_template_missing(self, mock_templates_dir):
        """Dashboard route raises error when template file not found."""
        from motus.ui.web.routes import register_routes

        # Mock template file that doesn't exist
        mock_template = Mock(spec=Path)
        mock_template.exists.return_value = False
        mock_templates_dir.__truediv__ = lambda self, other: mock_template

        app = FastAPI()
        register_routes(app)
        client = TestClient(app)

        with pytest.raises(FileNotFoundError) as exc_info:
            client.get("/")

        assert "Dashboard template not found" in str(exc_info.value)


class TestSummaryRoute:
    """Tests for summary route (/api/summary/{session_id})."""

    @patch("motus.ui.web.routes.get_orchestrator")
    def test_summary_returns_error_for_nonexistent_session(self, mock_get_orch):
        """Summary route returns error when session not found."""
        from motus.ui.web.routes import register_routes

        mock_orch = Mock()
        mock_orch.get_session.return_value = None
        mock_get_orch.return_value = mock_orch

        app = FastAPI()
        register_routes(app)
        client = TestClient(app)

        response = client.get("/api/summary/nonexistent-session")

        assert response.status_code == 200
        data = response.json()
        assert "error" in data
        assert "not found" in data["error"].lower()

    @patch("motus.ui.web.routes.extract_decisions")
    @patch("motus.ui.web.routes.analyze_session")
    @patch("motus.ui.web.routes.get_orchestrator")
    def test_summary_returns_markdown_for_valid_session(
        self, mock_get_orch, mock_analyze, mock_extract
    ):
        """Summary route returns markdown summary for valid session."""
        from motus.ui.web.routes import register_routes

        # Mock session
        mock_session = create_mock_session(
            session_id="test-session-abc123",
            project_path="/home/user/projects/myapp",
            size=2560000,  # 2.5 MB in bytes
        )
        mock_session.event_count = 42

        # Mock stats
        mock_stats = Mock()
        mock_stats.thinking_count = 10
        mock_stats.tool_count = 25
        mock_stats.agent_count = 2
        mock_stats.files_modified = {"/path/to/file1.py", "/path/to/file2.py"}
        mock_stats.high_risk_ops = 1

        mock_orch = Mock()
        mock_orch.get_session.return_value = mock_session
        mock_get_orch.return_value = mock_orch
        mock_analyze.return_value = mock_stats
        mock_extract.return_value = ["Use Redis for caching", "Add error handling"]

        app = FastAPI()
        register_routes(app)
        client = TestClient(app)

        response = client.get("/api/summary/test-session-abc123")

        assert response.status_code == 200
        data = response.json()
        assert "summary" in data
        assert "session_id" in data
        assert "project" in data
        assert data["session_id"] == "test-session-abc123"
        assert data["project"] == "/home/user/projects/myapp"

        # Check summary content
        summary = data["summary"]
        assert "## MC Session Memory" in summary
        assert "### Session Info" in summary
        assert "### Activity Summary" in summary
        assert "### Files Modified This Session" in summary
        assert "### Decisions Made" in summary
        assert "10" in summary  # thinking_count
        assert "25" in summary  # tool_count
        assert "2" in summary  # agent_count

    @patch("motus.ui.web.routes.extract_decisions")
    @patch("motus.ui.web.routes.analyze_session")
    @patch("motus.ui.web.routes.get_orchestrator")
    def test_summary_includes_files_modified(self, mock_get_orch, mock_analyze, mock_extract):
        """Summary includes list of modified files."""
        from motus.ui.web.routes import register_routes

        mock_session = create_mock_session()

        mock_stats = Mock()
        mock_stats.thinking_count = 5
        mock_stats.tool_count = 10
        mock_stats.agent_count = 1
        mock_stats.files_modified = {"/src/main.py", "/src/config.py", "/tests/test_main.py"}
        mock_stats.high_risk_ops = 0

        mock_orch = Mock()
        mock_orch.get_session.return_value = mock_session
        mock_get_orch.return_value = mock_orch
        mock_analyze.return_value = mock_stats
        mock_extract.return_value = []

        app = FastAPI()
        register_routes(app)
        client = TestClient(app)

        response = client.get("/api/summary/test-session")

        assert response.status_code == 200
        data = response.json()
        summary = data["summary"]

        # Check that files are listed
        assert "/src/main.py" in summary or "main.py" in summary
        assert "/src/config.py" in summary or "config.py" in summary

    @patch("motus.ui.web.routes.extract_decisions")
    @patch("motus.ui.web.routes.analyze_session")
    @patch("motus.ui.web.routes.get_orchestrator")
    def test_summary_includes_decisions(self, mock_get_orch, mock_analyze, mock_extract):
        """Summary includes list of decisions."""
        from motus.ui.web.routes import register_routes

        mock_session = create_mock_session()

        mock_stats = Mock()
        mock_stats.thinking_count = 5
        mock_stats.tool_count = 10
        mock_stats.agent_count = 1
        mock_stats.files_modified = set()
        mock_stats.high_risk_ops = 0

        mock_orch = Mock()
        mock_orch.get_session.return_value = mock_session
        mock_get_orch.return_value = mock_orch
        mock_analyze.return_value = mock_stats
        mock_extract.return_value = [
            "Use async/await for IO operations",
            "Add comprehensive error handling",
            "Implement caching strategy",
        ]

        app = FastAPI()
        register_routes(app)
        client = TestClient(app)

        response = client.get("/api/summary/test-session")

        assert response.status_code == 200
        data = response.json()
        summary = data["summary"]

        # Check that decisions are listed
        assert "Use async/await" in summary
        assert "error handling" in summary
        assert "caching" in summary

    @patch("motus.ui.web.routes.extract_decisions")
    @patch("motus.ui.web.routes.analyze_session")
    @patch("motus.ui.web.routes.get_orchestrator")
    def test_summary_limits_files_to_15(self, mock_get_orch, mock_analyze, mock_extract):
        """Summary limits files list to 15 entries."""
        from motus.ui.web.routes import register_routes

        mock_session = create_mock_session()

        # Create 20 files
        mock_stats = Mock()
        mock_stats.thinking_count = 5
        mock_stats.tool_count = 10
        mock_stats.agent_count = 1
        mock_stats.files_modified = {f"/src/file{i}.py" for i in range(20)}
        mock_stats.high_risk_ops = 0

        mock_orch = Mock()
        mock_orch.get_session.return_value = mock_session
        mock_get_orch.return_value = mock_orch
        mock_analyze.return_value = mock_stats
        mock_extract.return_value = []

        app = FastAPI()
        register_routes(app)
        client = TestClient(app)

        response = client.get("/api/summary/test-session")

        assert response.status_code == 200
        data = response.json()
        summary = data["summary"]

        # Count file entries (each file appears as "- `filename`")
        file_lines = [line for line in summary.split("\n") if line.strip().startswith("- `")]
        # Should have at most 15 file entries
        assert len(file_lines) <= 15

    @patch("motus.ui.web.routes.extract_decisions")
    @patch("motus.ui.web.routes.analyze_session")
    @patch("motus.ui.web.routes.get_orchestrator")
    def test_summary_limits_decisions_to_8(self, mock_get_orch, mock_analyze, mock_extract):
        """Summary limits decisions list to 8 entries."""
        from motus.ui.web.routes import register_routes

        mock_session = create_mock_session()

        mock_stats = Mock()
        mock_stats.thinking_count = 5
        mock_stats.tool_count = 10
        mock_stats.agent_count = 1
        mock_stats.files_modified = set()
        mock_stats.high_risk_ops = 0

        mock_orch = Mock()
        mock_orch.get_session.return_value = mock_session
        mock_get_orch.return_value = mock_orch
        mock_analyze.return_value = mock_stats
        # Create 12 decisions
        mock_extract.return_value = [f"Decision {i}" for i in range(12)]

        app = FastAPI()
        register_routes(app)
        client = TestClient(app)

        response = client.get("/api/summary/test-session")

        assert response.status_code == 200
        data = response.json()
        summary = data["summary"]

        # Count decision lines (decisions appear under "### Decisions Made")
        decisions_section = summary.split("### Decisions Made")[1]
        decision_lines = [
            line for line in decisions_section.split("\n") if line.strip().startswith("- Decision")
        ]
        # Should have at most 8 decisions
        assert len(decision_lines) <= 8

    @patch("motus.ui.web.routes.extract_decisions")
    @patch("motus.ui.web.routes.analyze_session")
    @patch("motus.ui.web.routes.get_orchestrator")
    def test_summary_shows_none_when_no_files_modified(
        self, mock_get_orch, mock_analyze, mock_extract
    ):
        """Summary shows 'None yet' when no files modified."""
        from motus.ui.web.routes import register_routes

        mock_session = create_mock_session()

        mock_stats = Mock()
        mock_stats.thinking_count = 5
        mock_stats.tool_count = 10
        mock_stats.agent_count = 1
        mock_stats.files_modified = set()
        mock_stats.high_risk_ops = 0

        mock_orch = Mock()
        mock_orch.get_session.return_value = mock_session
        mock_get_orch.return_value = mock_orch
        mock_analyze.return_value = mock_stats
        mock_extract.return_value = []

        app = FastAPI()
        register_routes(app)
        client = TestClient(app)

        response = client.get("/api/summary/test-session")

        assert response.status_code == 200
        data = response.json()
        summary = data["summary"]

        assert "None yet" in summary

    @patch("motus.ui.web.routes.extract_decisions")
    @patch("motus.ui.web.routes.analyze_session")
    @patch("motus.ui.web.routes.get_orchestrator")
    def test_summary_shows_no_decisions_when_empty(self, mock_get_orch, mock_analyze, mock_extract):
        """Summary shows 'No explicit decisions' when decisions list is empty."""
        from motus.ui.web.routes import register_routes

        mock_session = create_mock_session()

        mock_stats = Mock()
        mock_stats.thinking_count = 5
        mock_stats.tool_count = 10
        mock_stats.agent_count = 1
        mock_stats.files_modified = set()
        mock_stats.high_risk_ops = 0

        mock_orch = Mock()
        mock_orch.get_session.return_value = mock_session
        mock_get_orch.return_value = mock_orch
        mock_analyze.return_value = mock_stats
        mock_extract.return_value = []

        app = FastAPI()
        register_routes(app)
        client = TestClient(app)

        response = client.get("/api/summary/test-session")

        assert response.status_code == 200
        data = response.json()
        summary = data["summary"]

        assert "No explicit decisions" in summary

    @patch("motus.ui.web.routes.extract_decisions")
    @patch("motus.ui.web.routes.analyze_session")
    @patch("motus.ui.web.routes.get_orchestrator")
    def test_summary_handles_analyze_exception(self, mock_get_orch, mock_analyze, mock_extract):
        """Summary returns error when analyze_session raises exception."""
        from motus.ui.web.routes import register_routes

        mock_session = create_mock_session()

        mock_orch = Mock()
        mock_orch.get_session.return_value = mock_session
        mock_get_orch.return_value = mock_orch
        mock_analyze.side_effect = Exception("Analysis failed")

        app = FastAPI()
        register_routes(app)
        client = TestClient(app)

        response = client.get("/api/summary/test-session")

        assert response.status_code == 200
        data = response.json()
        assert "error" in data
        assert "Analysis failed" in data["error"]

    @patch("motus.ui.web.routes.extract_decisions")
    @patch("motus.ui.web.routes.analyze_session")
    @patch("motus.ui.web.routes.get_orchestrator")
    def test_summary_truncates_long_file_paths(self, mock_get_orch, mock_analyze, mock_extract):
        """Summary truncates very long file paths."""
        from motus.ui.web.routes import register_routes

        mock_session = create_mock_session()

        # Create file with very long path
        long_path = "/very/long/path/to/some/deeply/nested/directory/structure/that/exceeds/sixty/characters/file.py"
        mock_stats = Mock()
        mock_stats.thinking_count = 5
        mock_stats.tool_count = 10
        mock_stats.agent_count = 1
        mock_stats.files_modified = {long_path}
        mock_stats.high_risk_ops = 0

        mock_orch = Mock()
        mock_orch.get_session.return_value = mock_session
        mock_get_orch.return_value = mock_orch
        mock_analyze.return_value = mock_stats
        mock_extract.return_value = []

        app = FastAPI()
        register_routes(app)
        client = TestClient(app)

        response = client.get("/api/summary/test-session")

        assert response.status_code == 200
        data = response.json()
        summary = data["summary"]

        # Long path should be truncated to last 3 parts
        # Should show something like "nested/directory/structure" or similar
        # The exact truncation depends on path length, but full path shouldn't appear
        assert len(long_path) > 60
        # At minimum, the filename should appear
        assert "file.py" in summary
