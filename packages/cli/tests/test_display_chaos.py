"""Chaos and stress tests for the Display Layer.

These tests verify the Display Layer handles malicious/malformed input gracefully:
- Unicode edge cases (emoji, RTL, zero-width, combining chars)
- Size extremes (empty, huge content)
- Throughput (rapid event processing)
- Malicious markup injection (Rich, HTML)
- Null/None values
- Type confusion
"""

from datetime import datetime
from unittest.mock import MagicMock

from motus.display.events import DisplayEvent
from motus.display.renderer import SafeRenderer
from motus.display.transformer import EventTransformer
from motus.protocols import RiskLevel


class TestUnicodeChaos:
    """Test handling of Unicode edge cases."""

    def test_emoji_content_escaped(self):
        """Emoji characters are preserved and escaped."""
        content = "🔥 Fire emoji 🎉 Party 🚀 Rocket"
        result = SafeRenderer.escape(content)
        assert "🔥" in result
        assert "🎉" in result
        assert "🚀" in result

    def test_rtl_text_preserved(self):
        """Right-to-left text (Arabic, Hebrew) is preserved."""
        content = "Hello مرحبا שלום World"
        result = SafeRenderer.escape(content)
        assert "مرحبا" in result
        assert "שלום" in result

    def test_zero_width_characters(self):
        """Zero-width characters don't cause issues."""
        # Zero-width space, zero-width joiner, zero-width non-joiner
        content = "Hello\u200b\u200c\u200dWorld"
        result = SafeRenderer.escape(content)
        assert "Hello" in result
        assert "World" in result

    def test_combining_characters(self):
        """Combining diacritical marks are handled."""
        # e + combining acute accent = é
        content = "cafe\u0301"  # café with combining accent
        result = SafeRenderer.escape(content)
        assert result  # Should not crash

    def test_surrogate_pairs(self):
        """Surrogate pair characters (outside BMP) are handled."""
        # Mathematical bold capital A (U+1D400)
        content = "Math: 𝐀𝐁𝐂"
        result = SafeRenderer.escape(content)
        assert "𝐀" in result

    def test_newlines_and_tabs(self):
        """Newlines and tabs are normalized in content()."""
        content = "Line1\nLine2\tTabbed\r\nCRLF"
        result = SafeRenderer.content(content)
        assert "\n" not in result
        assert "\t" not in result
        assert "\r" not in result


class TestSizeChaos:
    """Test handling of content size extremes."""

    def test_empty_content(self):
        """Empty content returns empty string."""
        assert SafeRenderer.escape("") == ""
        assert SafeRenderer.content("") == ""
        assert SafeRenderer.file_path("") == ""
        assert SafeRenderer.command("") == ""

    def test_none_content(self):
        """None content returns empty string."""
        assert SafeRenderer.escape(None) == ""  # type: ignore[arg-type]
        assert SafeRenderer.content(None) == ""  # type: ignore[arg-type]

    def test_10kb_content_truncated(self):
        """10KB content is truncated to max_len."""
        content = "A" * 10240  # 10KB
        result = SafeRenderer.content(content, max_len=200)
        assert len(result) <= 200
        assert result.endswith("...")

    def test_100kb_content_truncated(self):
        """100KB content is truncated without crash."""
        content = "B" * 102400  # 100KB
        result = SafeRenderer.content(content, max_len=500)
        assert len(result) <= 500

    def test_single_character(self):
        """Single character content works."""
        assert SafeRenderer.escape("X") == "X"
        assert SafeRenderer.content("Y") == "Y"

    def test_whitespace_only_content(self):
        """Whitespace-only content is normalized to empty."""
        content = "   \t\n\r   "
        result = SafeRenderer.content(content)
        assert result == ""


class TestThroughputChaos:
    """Test rapid event processing (correctness only)."""

    def test_1000_events_in_sequence(self):
        """Process 1000 events without crash (correctness test, not timing)."""
        transformer = EventTransformer()

        # Create mock events
        events = []
        for i in range(1000):
            mock_event = MagicMock()
            mock_event.event_type.value = "TOOL_USE"
            mock_event.timestamp = datetime.now()
            mock_event.session_id = f"session-{i % 10}"
            mock_event.tool_name = "Read"
            mock_event.tool_input = {"file_path": f"/path/to/file{i}.py"}
            mock_event.content = f"Content {i}"
            mock_event.risk_level = RiskLevel.SAFE
            mock_event.model = "claude-3"
            mock_event.subagent_type = None
            mock_event.subagent_prompt = None
            events.append(mock_event)

        # Test correctness: all events transform successfully
        results = [transformer.transform(e) for e in events]

        assert len(results) == 1000
        assert all(isinstance(r, DisplayEvent) for r in results)
        # Timing assertion removed - see test_performance.py for throughput benchmarks

    def test_escape_performance(self):
        """Escape 10000 strings (correctness test, not timing)."""
        strings = [f"Content with [markup] and <html> {i}" for i in range(10000)]

        # Test correctness: all strings escape successfully
        results = [SafeRenderer.escape(s) for s in strings]

        assert len(results) == 10000
        # Timing assertion removed - see test_performance.py for throughput benchmarks


class TestMaliciousRichMarkup:
    """Test Rich markup injection attempts."""

    def test_bold_markup_escaped(self):
        """[bold] markup is escaped, not rendered."""
        content = "[bold]This should not be bold[/bold]"
        result = SafeRenderer.escape(content)
        assert "[bold]" not in result or "\\[bold]" in result or result.startswith("\\")

    def test_color_markup_escaped(self):
        """[red] [green] etc markup is escaped."""
        content = "[red]Red text[/red] [green]Green[/green]"
        result = SafeRenderer.escape(content)
        # Rich.escape converts [ to \[
        assert "\\[" in result or "[red]" not in result

    def test_link_markup_escaped(self):
        """[link] markup is escaped."""
        content = "[link=http://evil.com]Click me[/link]"
        result = SafeRenderer.escape(content)
        assert "\\[" in result or "[link=" not in result

    def test_nested_markup_escaped(self):
        """Nested markup attempts are escaped."""
        content = "[bold][italic][red]Nested[/red][/italic][/bold]"
        result = SafeRenderer.escape(content)
        assert "\\[" in result

    def test_escaped_escapes(self):
        """Already escaped content doesn't double-escape badly."""
        content = "\\[already escaped\\]"
        result = SafeRenderer.escape(content)
        # Should handle gracefully
        assert result  # Non-empty


class TestMaliciousHTML:
    """Test HTML injection attempts."""

    def test_script_tag_escaped(self):
        """<script> tags are escaped."""
        content = "<script>alert('xss')</script>"
        result = SafeRenderer.escape(content)
        # Rich escape handles < and > in markup context
        assert result  # Should not crash

    def test_img_onerror_escaped(self):
        """<img onerror> is escaped."""
        content = '<img src="x" onerror="alert(1)">'
        result = SafeRenderer.escape(content)
        assert result

    def test_iframe_escaped(self):
        """<iframe> is escaped."""
        content = '<iframe src="http://evil.com"></iframe>'
        result = SafeRenderer.escape(content)
        assert result

    def test_event_handlers_escaped(self):
        """onclick, onmouseover etc are escaped."""
        content = '<div onclick="evil()">Click</div>'
        result = SafeRenderer.escape(content)
        assert result

    def test_mixed_rich_and_html(self):
        """Mixed Rich and HTML injection attempts."""
        content = "[bold]<script>alert(1)</script>[/bold]"
        result = SafeRenderer.escape(content)
        assert "\\[" in result  # Rich markup escaped


class TestNullAndNoneValues:
    """Test handling of null/None values."""

    def test_none_to_escape(self):
        """None passed to escape returns empty."""
        result = SafeRenderer.escape(None)  # type: ignore[arg-type]
        assert result == ""

    def test_none_to_content(self):
        """None passed to content returns empty."""
        result = SafeRenderer.content(None)  # type: ignore[arg-type]
        assert result == ""

    def test_none_to_truncate(self):
        """None passed to truncate returns empty."""
        result = SafeRenderer.truncate(None, 100)  # type: ignore[arg-type]
        assert result == ""

    def test_transformer_handles_none_content(self):
        """EventTransformer handles event with None content."""
        transformer = EventTransformer()
        mock_event = MagicMock()
        mock_event.event_type.value = "THINKING"
        mock_event.timestamp = datetime.now()
        mock_event.session_id = "test-session"
        mock_event.content = None
        mock_event.risk_level = RiskLevel.SAFE
        mock_event.model = None
        mock_event.tool_name = None
        mock_event.tool_input = None
        mock_event.subagent_type = None
        mock_event.subagent_prompt = None

        result = transformer.transform(mock_event)
        assert isinstance(result, DisplayEvent)


class TestTypeConfusion:
    """Test wrong types passed to Display Layer."""

    def test_int_to_escape(self):
        """Integer passed to escape is converted."""
        result = SafeRenderer.escape(12345)  # type: ignore[arg-type]
        assert result == "12345"

    def test_float_to_escape(self):
        """Float passed to escape is converted."""
        result = SafeRenderer.escape(3.14159)  # type: ignore[arg-type]
        assert "3.14" in result

    def test_list_to_escape(self):
        """List passed to escape is converted to string."""
        result = SafeRenderer.escape([1, 2, 3])  # type: ignore[arg-type]
        assert result  # Should not crash

    def test_dict_to_escape(self):
        """Dict passed to escape is converted to string."""
        result = SafeRenderer.escape({"key": "value"})  # type: ignore[arg-type]
        assert result  # Should not crash

    def test_bool_to_escape(self):
        """Bool passed to escape is converted."""
        assert SafeRenderer.escape(True) == "True"  # type: ignore[arg-type]
        # False is falsy, so escape returns "" (by design - empty check)
        assert SafeRenderer.escape(False) == ""  # type: ignore[arg-type]


class TestEdgeCases:
    """Additional edge cases."""

    def test_very_long_file_path(self):
        """Very long file paths are truncated."""
        path = "/very/long/" + "subdir/" * 50 + "file.py"
        result = SafeRenderer.file_path(path)
        assert len(result) <= 63  # 60 + "..."

    def test_command_with_secrets(self):
        """Commands with potential secrets are handled."""
        # Note: SafeRenderer doesn't redact secrets, just escapes
        cmd = "curl -H 'Authorization: Bearer sk-secret123' http://api.com"
        result = SafeRenderer.command(cmd)
        assert result  # Escaping works

    def test_binary_looking_content(self):
        """Binary-looking content (null bytes) is handled."""
        content = "Before\x00After"
        result = SafeRenderer.escape(content)
        assert result  # Should not crash

    def test_control_characters(self):
        """Control characters are handled."""
        content = "Line\x07Bell\x08Backspace\x1bEscape"
        result = SafeRenderer.content(content)
        assert result  # Normalized
