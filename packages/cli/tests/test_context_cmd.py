"""Tests for context_cmd module (context display command)."""

from unittest.mock import MagicMock, patch

from motus.commands.context_cmd import context_command


class TestContextCommand:
    """Test context_command function."""

    def test_context_command_no_session_id_no_active(self):
        """Test context command with no session ID and no active sessions."""
        with patch("motus.commands.context_cmd.find_active_session", return_value=None):
            with patch("motus.commands.context_cmd.console") as mock_console:
                context_command()
                # Should print "No recent sessions found"
                assert mock_console.print.called

    def test_context_command_with_session_id_found(self):
        """Test context command with specific session ID that exists."""
        mock_session = MagicMock()
        mock_session.session_id = "test-12345"

        with patch(
            "motus.commands.context_cmd.find_claude_sessions", return_value=[mock_session]
        ):
            with patch(
                "motus.commands.context_cmd.generate_agent_context",
                return_value="# Context",
            ):
                with patch("motus.commands.context_cmd.console") as mock_console:
                    context_command(session_id="test-123")
                    # Should display context
                    assert mock_console.print.called

    def test_context_command_with_session_id_not_found(self):
        """Test context command with session ID that doesn't exist."""
        mock_session = MagicMock()
        mock_session.session_id = "other-session"

        with patch(
            "motus.commands.context_cmd.find_claude_sessions", return_value=[mock_session]
        ):
            with patch("motus.commands.context_cmd.console") as mock_console:
                context_command(session_id="test-123")
                # Should print "Session not found"
                assert mock_console.print.called

    def test_context_command_without_session_id(self):
        """Test context command without session ID (uses active session)."""
        mock_session = MagicMock()
        mock_session.session_id = "active-session"

        with patch(
            "motus.commands.context_cmd.find_active_session", return_value=mock_session
        ):
            with patch(
                "motus.commands.context_cmd.generate_agent_context",
                return_value="# Context",
            ):
                with patch("motus.commands.context_cmd.console") as mock_console:
                    context_command()
                    # Should display context
                    assert mock_console.print.called

    def test_context_command_generates_context(self):
        """Test that context command actually generates context."""
        mock_session = MagicMock()
        mock_session.session_id = "test-123"

        test_context = "## Motus Session Context\n\n**Session ID:** test-123"

        with patch(
            "motus.commands.context_cmd.find_active_session", return_value=mock_session
        ):
            with patch(
                "motus.commands.context_cmd.generate_agent_context",
                return_value=test_context,
            ) as mock_gen:
                with patch("motus.commands.context_cmd.console"):
                    context_command()
                    # Should call generate_agent_context
                    mock_gen.assert_called_once_with(mock_session)

    def test_context_command_empty_session_list(self):
        """Test context command with empty session list."""
        with patch("motus.commands.context_cmd.find_claude_sessions", return_value=[]):
            with patch("motus.commands.context_cmd.console") as mock_console:
                context_command(session_id="test-123")
                # Should print "Session not found"
                assert mock_console.print.called

    def test_context_command_partial_session_id_match(self):
        """Test context command matches session ID with prefix."""
        mock_session = MagicMock()
        mock_session.session_id = "test-12345-full-id"

        with patch(
            "motus.commands.context_cmd.find_claude_sessions", return_value=[mock_session]
        ):
            with patch(
                "motus.commands.context_cmd.generate_agent_context",
                return_value="# Context",
            ):
                with patch("motus.commands.context_cmd.console") as mock_console:
                    # Should match with partial ID
                    context_command(session_id="test-123")
                    assert mock_console.print.called
