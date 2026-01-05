# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""
FastAPI application setup for Motus Web UI.

Creates and configures the FastAPI app with middleware and routes.
"""

from __future__ import annotations

import socket
import threading
import time
import webbrowser
from pathlib import Path
from typing import TYPE_CHECKING, Optional

# Check for optional dependencies
try:
    import uvicorn
    from fastapi import FastAPI, WebSocket
    from fastapi.staticfiles import StaticFiles

    WEB_AVAILABLE = True
except ImportError:
    WEB_AVAILABLE = False

if TYPE_CHECKING:
    from fastapi.staticfiles import StaticFiles

from motus.logging import get_logger
from motus.hardening.package_conflicts import detect_package_conflicts
from motus.ui.web.routes import register_routes
from motus.ui.web.state import SessionState
from motus.ui.web.websocket import WebSocketHandler
from motus.ui.web.websocket_manager import WebSocketManager

logger = get_logger(__name__)

# Static files and template paths
UI_DIR = Path(__file__).parent.parent
STATIC_DIR = UI_DIR / "static"


class MCWebServer:
    """Lightweight WebSocket server for Motus Web UI."""

    def __init__(self, port: int = 4000):
        """Initialize web server.

        Args:
            port: Port to run on (0 = auto-assign)
        """
        self.port = port or self._find_free_port()
        self.app: FastAPI | None = None
        self.ws_manager = WebSocketManager()
        self.session_state = SessionState()
        self.ws_handler = WebSocketHandler(self.ws_manager, self.session_state)
        self.running = False

        # Legacy attributes for backward compatibility
        self.session_positions = self.session_state.session_positions
        self.session_contexts = self.session_state.session_contexts
        self.agent_stacks = self.session_state.agent_stacks
        self.parsing_errors = self.session_state.parsing_errors

    def _find_free_port(self) -> int:
        """Find an available port.

        In sandboxed CI environments, socket binding may be restricted.
        Falls back to a non-privileged default port if dynamic allocation fails.
        """
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("127.0.0.1", 0))
                return s.getsockname()[1]
        except OSError:
            # Sandboxed environment - return default port
            return 4000

    def _prune_session_dicts(self, active_session_ids: set[str]) -> None:
        """Backward compatibility wrapper for session state pruning."""
        self.session_state.prune_session_dicts(active_session_ids)

    def _get_cached_sessions(self):
        """Backward compatibility wrapper for cached sessions."""
        return self.session_state.get_cached_sessions()

    def create_app(self) -> FastAPI:
        """Create the FastAPI application."""
        if not WEB_AVAILABLE:
            raise RuntimeError("Web dependencies are not installed")

        app = FastAPI(title="Motus Web UI")

        # Security headers middleware (local-only, but defense in depth)
        @app.middleware("http")
        async def add_security_headers(request, call_next):
            response = await call_next(request)
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline'; "
                "style-src 'self' 'unsafe-inline'; "
                "connect-src 'self' ws://localhost:* ws://127.0.0.1:*"
            )
            return response

        # Mount static files directory
        if STATIC_DIR.exists():
            app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

        # Register HTTP routes
        register_routes(app)

        # WebSocket endpoint
        @app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            await self.ws_handler.handle_connection(websocket)

        return app

    def run(self, open_browser: bool = True):
        """Run the web server.

        Args:
            open_browser: Whether to open browser automatically

        Returns:
            True if successful, False if web dependencies not available
        """
        if not WEB_AVAILABLE:
            print("Web dependencies not installed.")
            print("Install with: pip install motusos[web]")
            print("\nFalling back to CLI mode...")
            return False

        self.app = self.create_app()

        print(f"🔮 Motus Web UI starting on http://localhost:{self.port}")

        if open_browser:
            # Open browser after short delay
            def open_delayed():
                time.sleep(0.5)
                webbrowser.open(f"http://localhost:{self.port}")

            threading.Thread(target=open_delayed, daemon=True).start()

        try:
            uvicorn.run(
                self.app,
                host="127.0.0.1",
                port=self.port,
                log_level="warning",
            )
        except KeyboardInterrupt:
            print("\n👋 Motus Web UI stopped")

        return True


def run_web(port: Optional[int] = None, no_browser: bool = False):
    """Entry point for motus web command.

    Args:
        port: Port to run on (None = 4000)
        no_browser: If True, don't open browser automatically
    """
    conflict = detect_package_conflicts()
    if conflict.conflict:
        print("Package conflict detected. Motus is loading from a conflicting installation.")
        if conflict.conflicts:
            installed = ", ".join(f"{name}=={ver}" for name, ver in conflict.conflicts.items())
            print(f"Conflicting packages: {installed}")
        if conflict.origin:
            print(f"Import origin: {conflict.origin}")
        print("Fix: pip uninstall motus motus-command -y")
        print("Then reinstall: pip install motusos[web]")
        raise SystemExit(1)

    server = MCWebServer(port=port if port is not None else 4000)
    success = server.run(open_browser=not no_browser)
    if not success:
        raise SystemExit(1)
