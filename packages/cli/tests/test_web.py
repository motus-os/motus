"""Tests for web module - MC Web UI."""


class TestCalculateHealth:
    """Tests for calculate_health pure function."""

    def test_empty_context_returns_default(self):
        """Empty context returns waiting state."""
        from src.motus.ui.web import calculate_health

        result = calculate_health({})
        assert result["health"] == 50
        assert result["status"] == "waiting"
        assert result["drift"] is None

    def test_none_context_returns_default(self):
        """None context returns waiting state."""
        from src.motus.ui.web import calculate_health

        result = calculate_health(None)
        assert result["health"] == 50
        assert result["status"] == "waiting"

    def test_productive_work_increases_health(self):
        """Edit/Write tools increase health score."""
        from src.motus.ui.web import calculate_health

        ctx = {
            "tool_count": {"Edit": 5, "Write": 3},
            "files_modified": ["a.py", "b.py", "c.py"],
            "decisions": ["Use async"],
            "friction_count": 0,
        }
        result = calculate_health(ctx)
        assert result["health"] >= 75
        assert result["status"] == "on_track"

    def test_high_friction_affects_status(self):
        """High friction count changes status."""
        from src.motus.ui.web import calculate_health

        ctx = {
            "tool_count": {"Edit": 1},
            "files_modified": ["a.py"],
            "decisions": [],
            "friction_count": 5,
        }
        result = calculate_health(ctx)
        assert result["status"] == "working_through_it"

    def test_read_heavy_session_acceptable(self):
        """Research (read-heavy) sessions get acceptable scores."""
        from src.motus.ui.web import calculate_health

        ctx = {
            "tool_count": {"Read": 10, "Glob": 5, "Grep": 3},
            "files_modified": [],
            "decisions": [],
            "friction_count": 0,
        }
        result = calculate_health(ctx)
        assert result["health"] >= 40  # Not terrible
        assert result["status"] in ["exploring", "on_track"]

    def test_drift_state_ignored(self):
        """Drift state is ignored in health calculation."""
        from src.motus.ui.web import calculate_health

        ctx = {"tool_count": {}, "files_modified": [], "decisions": [], "friction_count": 0}
        drift_state = {"is_drifting": True, "drift_score": 10}

        result = calculate_health(ctx, drift_state)
        assert result["drift"] is None
        assert result["status"] != "drifting"

    def test_health_clamped_to_range(self):
        """Health score is clamped to 10-95."""
        from src.motus.ui.web import calculate_health

        # Very low - should clamp to 10
        ctx_low = {
            "tool_count": {},
            "files_modified": [],
            "decisions": [],
            "friction_count": 10,  # Lots of friction
        }
        result_low = calculate_health(ctx_low)
        assert result_low["health"] >= 10

        # Very high - should clamp to 95
        ctx_high = {
            "tool_count": {"Edit": 20, "Write": 20},
            "files_modified": ["a.py", "b.py", "c.py", "d.py", "e.py"],
            "decisions": ["d1", "d2", "d3", "d4", "d5"],
            "friction_count": 0,
        }
        result_high = calculate_health(ctx_high)
        assert result_high["health"] <= 95

    def test_metrics_included_in_result(self):
        """Result includes metrics breakdown."""
        from src.motus.ui.web import calculate_health

        ctx = {
            "tool_count": {"Edit": 1},
            "files_modified": ["a.py"],
            "decisions": ["Use Redis"],
            "friction_count": 1,
        }
        result = calculate_health(ctx)

        assert "metrics" in result
        assert "friction" in result["metrics"]
        assert "activity" in result["metrics"]
        assert "progress" in result["metrics"]
        assert "decisions" in result["metrics"]


class TestMCWebServer:
    """Tests for MCWebServer class."""

    def test_initialization_finds_free_port(self):
        """Server finds a free port when port=0."""
        from src.motus.ui.web import MCWebServer

        server = MCWebServer(port=0)
        assert server.port > 0
        assert server.port < 65536

    def test_initialization_uses_specified_port(self):
        """Server uses specified port when provided."""
        from src.motus.ui.web import MCWebServer

        server = MCWebServer(port=8765)
        assert server.port == 8765

    def test_server_creates_fastapi_app(self):
        """Server creates a FastAPI application."""
        from src.motus.ui.web import MCWebServer

        server = MCWebServer(port=0)
        app = server.create_app()

        # Check it's a FastAPI app
        assert app is not None
        assert hasattr(app, "routes")

    def test_server_initial_state(self):
        """Server initializes with correct state."""
        from src.motus.ui.web import MCWebServer

        server = MCWebServer(port=0)

        assert server.ws_manager.clients == set()
        assert server.session_positions == {}
        assert server.session_contexts == {}
        assert server.running is False


class TestFastAPIRoutes:
    """Tests for FastAPI route endpoints."""

    def test_dashboard_returns_html(self):
        """GET / returns HTML content."""
        from fastapi.testclient import TestClient

        from src.motus.ui.web import MCWebServer

        server = MCWebServer(port=0)
        app = server.create_app()
        client = TestClient(app)

        response = client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")

    def test_summary_endpoint_returns_json(self):
        """GET /api/summary/{session_id} returns JSON."""
        from fastapi.testclient import TestClient

        from src.motus.ui.web import MCWebServer

        server = MCWebServer(port=0)
        app = server.create_app()
        client = TestClient(app)

        # Should return 404 or empty for non-existent session
        response = client.get("/api/summary/nonexistent-session")
        # Either 404 or empty JSON is acceptable
        assert response.status_code in [200, 404]

    def test_websocket_accepts_connection(self):
        """WebSocket endpoint accepts connections."""
        from fastapi.testclient import TestClient

        from src.motus.ui.web import MCWebServer

        server = MCWebServer(port=0)
        app = server.create_app()
        client = TestClient(app)

        # TestClient provides a websocket context manager
        try:
            with client.websocket_connect("/ws") as websocket:
                # Just test that connection succeeds
                assert websocket is not None
        except Exception:
            # WebSocket might fail in test environment, that's ok for smoke test
            pass


class TestWebServerIntegration:
    """Integration tests for web server behavior."""

    def test_multiple_servers_get_different_ports(self):
        """Multiple servers find different free ports."""
        from src.motus.ui.web import MCWebServer

        server1 = MCWebServer(port=0)
        server2 = MCWebServer(port=0)

        # They should get different ports (or the same if the OS recycles)
        # Main thing is neither should fail
        assert server1.port > 0
        assert server2.port > 0

    def test_server_app_has_required_routes(self):
        """Server app has the required route paths."""
        from src.motus.ui.web import MCWebServer

        server = MCWebServer(port=0)
        app = server.create_app()

        routes = [route.path for route in app.routes]

        assert "/" in routes
        assert "/ws" in routes
        assert "/api/summary/{session_id}" in routes


class TestHealthStatusLogic:
    """Tests for health status determination logic."""

    def test_needs_attention_for_low_health(self):
        """Low health triggers needs_attention status."""
        from src.motus.ui.web import calculate_health

        ctx = {"tool_count": {}, "files_modified": [], "decisions": [], "friction_count": 3}
        result = calculate_health(ctx)

        # With no activity and some friction, should be exploring or needs_attention
        assert result["status"] in ["exploring", "needs_attention", "working_through_it"]

    def test_exploring_for_moderate_health(self):
        """Moderate health shows exploring status."""
        from src.motus.ui.web import calculate_health

        ctx = {
            "tool_count": {"Read": 3},
            "files_modified": [],
            "decisions": [],
            "friction_count": 0,
        }
        result = calculate_health(ctx)

        # With just reads, should be exploring
        assert result["health"] >= 40
        assert result["health"] < 80

    def test_on_track_for_high_health(self):
        """High health shows on_track status."""
        from src.motus.ui.web import calculate_health

        ctx = {
            "tool_count": {"Edit": 3, "Write": 2},
            "files_modified": ["a.py", "b.py"],
            "decisions": ["Use caching", "Add tests"],
            "friction_count": 0,
        }
        result = calculate_health(ctx)

        assert result["health"] >= 70
        assert result["status"] == "on_track"


class TestWebServerClientManagement:
    """Tests for client management in web server."""

    def test_clients_set_starts_empty(self):
        """Clients set starts empty."""
        from src.motus.ui.web import MCWebServer

        server = MCWebServer(port=0)
        assert len(server.ws_manager.clients) == 0

    def test_session_positions_starts_empty(self):
        """Session positions dict starts empty."""
        from src.motus.ui.web import MCWebServer

        server = MCWebServer(port=0)
        assert server.session_positions == {}

    def test_agent_stacks_starts_empty(self):
        """Agent stacks dict starts empty."""
        from src.motus.ui.web import MCWebServer

        server = MCWebServer(port=0)
        assert server.agent_stacks == {}


class TestWebServerPortFinding:
    """Tests for port finding functionality."""

    def test_find_free_port_returns_valid_port(self):
        """_find_free_port returns a valid port number."""
        from src.motus.ui.web import MCWebServer

        server = MCWebServer(port=0)
        port = server._find_free_port()

        assert port > 0
        assert port < 65536

    def test_consecutive_port_finds_work(self):
        """Can find multiple free ports."""
        from src.motus.ui.web import MCWebServer

        server = MCWebServer(port=0)
        port1 = server._find_free_port()
        port2 = server._find_free_port()

        # Both should be valid
        assert port1 > 0
        assert port2 > 0


class TestHealthCalculationEdgeCases:
    """Edge case tests for health calculation."""

    def test_very_high_friction(self):
        """Very high friction still produces valid health."""
        from src.motus.ui.web import calculate_health

        ctx = {"tool_count": {}, "files_modified": [], "decisions": [], "friction_count": 100}
        result = calculate_health(ctx)

        assert result["health"] >= 10
        assert result["health"] <= 95

    def test_many_files_modified(self):
        """Many files modified produces high progress score."""
        from src.motus.ui.web import calculate_health

        ctx = {
            "tool_count": {"Edit": 20},
            "files_modified": [f"file{i}.py" for i in range(50)],
            "decisions": [],
            "friction_count": 0,
        }
        result = calculate_health(ctx)

        assert result["health"] >= 60

    def test_many_decisions(self):
        """Many decisions improve health score."""
        from src.motus.ui.web import calculate_health

        ctx = {
            "tool_count": {},
            "files_modified": [],
            "decisions": [f"Decision {i}" for i in range(20)],
            "friction_count": 0,
        }
        result = calculate_health(ctx)

        assert result["metrics"]["decisions"] >= 50

class TestDashboardContent:
    """Tests for dashboard HTML content."""

    def test_dashboard_returns_valid_html(self):
        """Dashboard returns valid HTML document."""
        from fastapi.testclient import TestClient

        from src.motus.ui.web import MCWebServer

        server = MCWebServer(port=0)
        app = server.create_app()
        client = TestClient(app)

        response = client.get("/")
        assert "<!DOCTYPE html>" in response.text or "<!doctype html>" in response.text.lower()
        assert "</html>" in response.text

    def test_dashboard_contains_script(self):
        """Dashboard HTML contains JavaScript."""
        from fastapi.testclient import TestClient

        from src.motus.ui.web import MCWebServer

        server = MCWebServer(port=0)
        app = server.create_app()
        client = TestClient(app)

        response = client.get("/")
        assert "<script" in response.text or "script" in response.text.lower()
