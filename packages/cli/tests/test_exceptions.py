"""Tests for the MC exceptions module."""


class TestMCError:
    """Test base MCError exception."""

    def test_basic_creation(self):
        """Test basic error creation."""
        from motus.exceptions import MCError

        error = MCError("Something went wrong")

        assert str(error) == "Something went wrong"
        assert error.message == "Something went wrong"
        assert error.details is None

    def test_with_details(self):
        """Test error with details."""
        from motus.exceptions import MCError

        error = MCError("Failed to connect", details="Connection refused")

        assert error.message == "Failed to connect"
        assert error.details == "Connection refused"
        assert str(error) == "Failed to connect: Connection refused"


class TestSessionError:
    """Test SessionError exception."""

    def test_with_session_id(self):
        """Test session error with session ID."""
        from motus.exceptions import SessionError

        error = SessionError("Session corrupted", session_id="abc123")

        assert error.session_id == "abc123"
        assert "Session corrupted" in str(error)

    def test_inheritance(self):
        """Test SessionError inherits from MCError."""
        from motus.exceptions import MCError, SessionError

        error = SessionError("Test error")

        assert isinstance(error, MCError)


class TestSessionNotFoundError:
    """Test SessionNotFoundError exception."""

    def test_creation(self):
        """Test error creation."""
        from motus.exceptions import SessionError, SessionNotFoundError

        error = SessionNotFoundError("Session not found", session_id="missing123")

        assert isinstance(error, SessionError)
        assert error.session_id == "missing123"


class TestSessionParseError:
    """Test SessionParseError exception."""

    def test_creation(self):
        """Test error creation."""
        from motus.exceptions import SessionError, SessionParseError

        error = SessionParseError("Invalid JSON", session_id="bad123")

        assert isinstance(error, SessionError)


class TestConfigError:
    """Test ConfigError exception."""

    def test_creation(self):
        """Test error creation."""
        from motus.exceptions import ConfigError, MCError

        error = ConfigError("Invalid port", details="Port must be > 0")

        assert isinstance(error, MCError)
        assert "Invalid port" in str(error)


class TestWebError:
    """Test WebError exception."""

    def test_creation(self):
        """Test error creation."""
        from motus.exceptions import MCError, WebError

        error = WebError("Server failed to start")

        assert isinstance(error, MCError)


class TestWebSocketError:
    """Test WebSocketError exception."""

    def test_inheritance(self):
        """Test WebSocketError inherits from WebError."""
        from motus.exceptions import WebError, WebSocketError

        error = WebSocketError("Connection dropped")

        assert isinstance(error, WebError)


class TestTranscriptError:
    """Test TranscriptError exception."""

    def test_creation(self):
        """Test error creation."""
        from motus.exceptions import MCError, TranscriptError

        error = TranscriptError("Failed to read transcript")

        assert isinstance(error, MCError)


class TestExceptionHierarchy:
    """Test the exception class hierarchy."""

    def test_all_inherit_from_mc_error(self):
        """Test all custom exceptions inherit from MCError."""
        from motus.exceptions import (
            ConfigError,
            DriftError,
            HookError,
            InvalidIntentError,
            InvalidSessionError,
            MCError,
            SessionError,
            SessionNotFoundError,
            SessionParseError,
            TracerError,
            TranscriptError,
            WebError,
            WebSocketError,
        )

        exceptions = [
            SessionError("test"),
            SessionNotFoundError("test"),
            SessionParseError("test"),
            ConfigError("test"),
            WebError("test"),
            WebSocketError("test"),
            TranscriptError("test"),
            TracerError("test"),
            HookError("test"),
            DriftError("test"),
            InvalidIntentError("test"),
            InvalidSessionError("test"),
        ]

        for exc in exceptions:
            assert isinstance(exc, MCError), f"{type(exc).__name__} should inherit from MCError"

    def test_can_catch_by_base_class(self):
        """Test exceptions can be caught by base class."""
        from motus.exceptions import MCError, SessionNotFoundError

        try:
            raise SessionNotFoundError("Not found", session_id="test")
        except MCError as e:
            assert e.message == "Not found"


class TestParseError:
    """Test ParseError exception."""

    def test_parse_error_basic(self):
        """Test ParseError with basic message."""
        from motus.exceptions import ParseError

        error = ParseError("Parse failed")
        assert error.message == "Parse failed"
        assert error.file_path is None
        assert error.line_number is None
        assert error.raw_content is None

    def test_parse_error_with_file_path(self):
        """Test ParseError with file path."""
        from motus.exceptions import ParseError

        error = ParseError("Parse failed", file_path="/path/to/file.jsonl")
        assert error.file_path == "/path/to/file.jsonl"
        assert "file=/path/to/file.jsonl" in str(error)

    def test_parse_error_with_line_number(self):
        """Test ParseError with line number."""
        from motus.exceptions import ParseError

        error = ParseError("Parse failed", line_number=42)
        assert error.line_number == 42
        assert "line=42" in str(error)

    def test_parse_error_with_raw_content(self):
        """Test ParseError with raw content."""
        from motus.exceptions import ParseError

        error = ParseError("Parse failed", raw_content='{"invalid": json}')
        assert error.raw_content == '{"invalid": json}'
        assert "content=" in str(error)

    def test_parse_error_truncates_long_content(self):
        """Test ParseError truncates raw content over 200 chars."""
        from motus.exceptions import ParseError

        long_content = "x" * 300
        error = ParseError("Parse failed", raw_content=long_content)
        assert len(error.raw_content) == 200
        assert error.raw_content == "x" * 200

    def test_parse_error_with_all_details(self):
        """Test ParseError with all detail fields."""
        from motus.exceptions import ParseError

        error = ParseError(
            "Parse failed",
            file_path="/session.jsonl",
            line_number=10,
            raw_content='{"bad": "json"}',
        )
        assert error.file_path == "/session.jsonl"
        assert error.line_number == 10
        assert error.raw_content == '{"bad": "json"}'

        error_str = str(error)
        assert "file=/session.jsonl" in error_str
        assert "line=10" in error_str
        assert "content=" in error_str

    def test_parse_error_format_details_empty(self):
        """Test ParseError._format_details with no details."""
        from motus.exceptions import ParseError

        error = ParseError("Parse failed")
        details = error._format_details()
        assert details is None


class TestTracerError:
    """Test TracerError exception."""

    def test_tracer_error_basic(self):
        """Test TracerError with basic message."""
        from motus.exceptions import TracerError

        error = TracerError("Tracer failed")
        assert error.message == "Tracer failed"
        assert isinstance(error, Exception)
