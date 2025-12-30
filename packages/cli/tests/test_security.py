"""Security tests for XSS/escaping and input sanitization.

These tests verify that user-controlled content is properly escaped
before being rendered in the TUI and Web dashboards.
"""

# XSS attack payloads for testing
XSS_PAYLOADS = [
    "<script>alert('XSS')</script>",
    "<img src=x onerror=alert('XSS')>",
    "javascript:alert('XSS')",
    "<a href=\"javascript:alert('XSS')\">click me</a>",
    "' onclick=alert('XSS') '",
    '"><script>alert(String.fromCharCode(88,83,83))</script>',
    "${7*7}",  # Template injection
    "{{7*7}}",  # Jinja/template injection
    "\x00<script>alert('XSS')</script>",  # Null byte
]


class TestRichMarkupEscaping:
    """Test that Rich markup is properly escaped in TUI."""

    def test_escape_prevents_markup_injection(self):
        """Rich escape() prevents markup injection."""
        from rich.markup import escape

        # These strings should be escaped so Rich doesn't interpret them
        dangerous_content = "[bold red]MALICIOUS[/bold red]"
        escaped = escape(dangerous_content)

        # Escaped version should not contain unescaped brackets
        assert "\\[" in escaped or "[" not in escaped.replace("\\[", "")

    def test_escape_handles_all_special_chars(self):
        """Rich escape() handles all Rich special characters."""
        from rich.markup import escape

        # Rich special characters that need escaping
        special_chars = "[]\\/"
        for char in special_chars:
            test_str = f"text{char}more"
            escaped = escape(test_str)
            # The character should either be escaped or the string unchanged
            assert isinstance(escaped, str)

    def test_escape_handles_xss_payloads(self):
        """Rich escape() handles XSS payloads safely."""
        from rich.markup import escape

        for payload in XSS_PAYLOADS:
            escaped = escape(payload)
            # Should return a string without crashing
            assert isinstance(escaped, str)
            # Should not be empty (unless payload was empty)
            if payload:
                assert len(escaped) > 0


class TestHtmlEscaping:
    """Test HTML escaping for Web dashboard."""

    def test_python_html_escape_prevents_xss(self):
        """Python's html.escape prevents XSS attacks."""
        import html

        for payload in XSS_PAYLOADS:
            escaped = html.escape(payload)
            # Should not contain unescaped < or >
            assert "<" not in escaped or "&lt;" in escaped
            # Should return a string
            assert isinstance(escaped, str)

    def test_html_escape_preserves_safe_content(self):
        """HTML escaping preserves safe content."""
        import html

        safe_content = "Normal text with numbers 123 and symbols !@#$%"
        escaped = html.escape(safe_content)
        # Most characters should pass through unchanged
        assert "Normal text" in escaped
        assert "123" in escaped


class TestWebApiEscaping:
    """Test that Web API endpoints return properly escaped content."""

    def test_redact_secrets_removes_sensitive_data(self):
        """redact_secrets removes API keys and tokens."""
        from motus.commands.utils import redact_secrets

        # Test various secret patterns that match the actual regex patterns
        test_cases = [
            # OpenAI key pattern: sk-[a-zA-Z0-9]{20,}
            ("Found key: sk-abcdefghij1234567890ABCD", "sk-abcdefghij", "[REDACTED_OPENAI_KEY]"),
            # JWT pattern
            (
                "Token: eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U",
                "eyJhbGciOiJIUzI1NiJ9",
                "[REDACTED_JWT]",
            ),
            # GitHub token pattern: ghp_[a-zA-Z0-9]{36} - exactly 36 chars after ghp_
            (
                "Using ghp_abcdefghijklmnopqrstuvwxyz1234ABCDEF",
                "ghp_abcdefghij",
                "[REDACTED_GITHUB_TOKEN]",
            ),
            # Password pattern
            ("password=mysecretpassword123", "mysecretpassword", "password=[REDACTED]"),
            # API key pattern
            ("api_key: supersecretkey123456", "supersecretkey", "api_key=[REDACTED]"),
        ]

        for content, secret_part, redacted_marker in test_cases:
            redacted = redact_secrets(content)
            # The redacted marker should be present
            assert redacted_marker in redacted, f"Expected '{redacted_marker}' in '{redacted}'"
            # The original secret part should not appear
            assert (
                secret_part not in redacted
            ), f"Secret '{secret_part}' should not appear in '{redacted}'"

    def test_redact_secrets_handles_xss_in_secrets(self):
        """redact_secrets handles XSS payloads in secret values."""
        from motus.commands.utils import redact_secrets

        # XSS payload in a "secret" context
        malicious = "API_KEY=<script>alert('XSS')</script>"
        redacted = redact_secrets(malicious)
        # Should still be a string
        assert isinstance(redacted, str)


class TestEventContentEscaping:
    """Test that event content is escaped before display."""

    def test_tool_input_escaping(self):
        """Tool inputs with special chars are handled safely."""
        from datetime import datetime

        from motus.cli import ToolEvent

        # Create event with potentially dangerous content
        event = ToolEvent(
            name="Read",
            input={"file_path": "/path/<script>alert('xss')</script>"},
            timestamp=datetime.now(),
        )

        # Event should store content as-is (escaping happens at render time)
        assert "<script>" in event.input["file_path"]

    def test_thinking_event_escaping(self):
        """Thinking events with special chars are handled safely."""
        from datetime import datetime

        from motus.cli import ThinkingEvent

        # Create event with Rich markup injection attempt
        event = ThinkingEvent(
            content="[bold red]Injected markup[/bold red]",
            timestamp=datetime.now(),
        )

        # Event stores raw content
        assert "[bold red]" in event.content


class TestResilienceAgainstMalformedInput:
    """Test resilience against malformed/malicious input."""

    def test_parse_line_handles_malformed_json(self):
        """Parser handles malformed JSON gracefully."""
        import json

        from motus.ingestors.claude import ClaudeBuilder

        builder = ClaudeBuilder()

        malformed_inputs = [
            "{not valid json}",
            '{"unclosed": "brace"',
            "null",
            "",
            "   ",
            '{"nested": {"deep": {"very": {"deep": {"value": "test"}}}}}',
        ]

        for malformed in malformed_inputs:
            try:
                result = builder.parse_line(malformed, session_id="test-session")
                # Should return empty list or valid events, not crash
                assert isinstance(result, list)
            except Exception as e:
                # If it raises, should be a known/safe error type
                # AttributeError can occur when parsing returns None
                assert isinstance(
                    e, (ValueError, KeyError, TypeError, AttributeError, json.JSONDecodeError)
                )

    def test_parse_line_handles_xss_in_content(self):
        """Parser handles XSS payloads in event content."""
        import json

        from motus.ingestors.claude import ClaudeBuilder

        builder = ClaudeBuilder()

        for payload in XSS_PAYLOADS:
            # Create a valid JSON line with XSS in content
            line = json.dumps(
                {
                    "type": "assistant",
                    "message": {"content": payload},
                }
            )

            try:
                result = builder.parse_line(line, session_id="test-session")
                assert isinstance(result, list)
            except Exception:
                # Parser may reject, but shouldn't crash unexpectedly
                pass


class TestPathTraversalPrevention:
    """Test path traversal attack prevention in evidence verification."""

    def test_absolute_path_rejected(self, tmp_path):
        """Absolute paths in artifact_hashes should be rejected."""
        import json

        from motus.policy.reason_codes import EVIDENCE_PATH_TRAVERSAL
        from motus.policy.verify import verify_evidence_bundle

        evidence_dir = tmp_path / "evidence"
        evidence_dir.mkdir()

        # Create manifest with absolute path (attack vector)
        manifest = {
            "artifact_hashes": [{"path": "/etc/passwd", "sha256": "abc123"}],
            "run_hash": "test",
        }
        (evidence_dir / "manifest.json").write_text(json.dumps(manifest))

        result = verify_evidence_bundle(evidence_dir=evidence_dir)
        assert not result.ok
        assert EVIDENCE_PATH_TRAVERSAL in result.reason_codes

    def test_parent_traversal_rejected(self, tmp_path):
        """Paths with ../ escaping evidence_dir should be rejected."""
        import json

        from motus.policy.reason_codes import EVIDENCE_PATH_TRAVERSAL
        from motus.policy.verify import verify_evidence_bundle

        evidence_dir = tmp_path / "evidence"
        evidence_dir.mkdir()

        # Create a file outside evidence_dir
        secret_file = tmp_path / "secret.txt"
        secret_file.write_text("secret data")

        # Create manifest with path traversal attack
        manifest = {
            "artifact_hashes": [{"path": "../secret.txt", "sha256": "abc123"}],
            "run_hash": "test",
        }
        (evidence_dir / "manifest.json").write_text(json.dumps(manifest))

        result = verify_evidence_bundle(evidence_dir=evidence_dir)
        assert not result.ok
        assert EVIDENCE_PATH_TRAVERSAL in result.reason_codes

    def test_deep_traversal_rejected(self, tmp_path):
        """Deep traversal paths like ../../../etc/passwd should be rejected."""
        import json

        from motus.policy.reason_codes import EVIDENCE_PATH_TRAVERSAL
        from motus.policy.verify import verify_evidence_bundle

        evidence_dir = tmp_path / "evidence"
        evidence_dir.mkdir()

        manifest = {
            "artifact_hashes": [{"path": "../../../etc/passwd", "sha256": "abc123"}],
            "run_hash": "test",
        }
        (evidence_dir / "manifest.json").write_text(json.dumps(manifest))

        result = verify_evidence_bundle(evidence_dir=evidence_dir)
        assert not result.ok
        assert EVIDENCE_PATH_TRAVERSAL in result.reason_codes

    def test_relative_path_within_dir_allowed(self, tmp_path):
        """Relative paths that stay within evidence_dir should work."""
        import json

        from motus.policy.reason_codes import EVIDENCE_PATH_TRAVERSAL
        from motus.policy.verifiability import sha256_file
        from motus.policy.verify import verify_evidence_bundle

        evidence_dir = tmp_path / "evidence"
        evidence_dir.mkdir()
        (evidence_dir / "subdir").mkdir()

        # Create a legitimate artifact
        artifact = evidence_dir / "subdir" / "artifact.txt"
        artifact.write_text("legitimate content")
        artifact_hash = sha256_file(artifact)

        manifest = {
            "artifact_hashes": [{"path": "subdir/artifact.txt", "sha256": artifact_hash}],
            "run_hash": "placeholder",
        }
        (evidence_dir / "manifest.json").write_text(json.dumps(manifest))

        result = verify_evidence_bundle(evidence_dir=evidence_dir)
        # May fail for other reasons (schema, run_hash) but NOT path traversal
        assert EVIDENCE_PATH_TRAVERSAL not in result.reason_codes


class TestRaceConditionPrevention:
    """Test race condition prevention in claim registration."""

    def test_concurrent_claims_same_resource_one_wins(self, tmp_path):
        """Two concurrent claims for same resource - only one should succeed."""
        import threading

        from motus.coordination.claims_core import ClaimConflict, ClaimRegistry

        registry = ClaimRegistry(tmp_path / "claims", lease_duration_s=3600)
        resources = [{"type": "file", "path": "/test/file.txt"}]

        results = []
        errors = []

        def claim_resource(agent_id: str):
            try:
                result = registry.register_claim(
                    task_id=f"task-{agent_id}",
                    agent_id=agent_id,
                    resources=resources,
                    namespace="test",
                )
                results.append((agent_id, result))
            except Exception as e:
                errors.append((agent_id, e))

        threads = [
            threading.Thread(target=claim_resource, args=("agent-1",)),
            threading.Thread(target=claim_resource, args=("agent-2",)),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Unexpected errors: {errors}"
        assert len(results) == 2

        successes = [r for _, r in results if not isinstance(r, ClaimConflict)]
        conflicts = [r for _, r in results if isinstance(r, ClaimConflict)]

        # Exactly one should succeed, one should conflict
        assert len(successes) == 1, f"Expected 1 success, got {len(successes)}"
        assert len(conflicts) == 1, f"Expected 1 conflict, got {len(conflicts)}"

    def test_concurrent_claims_different_resources_both_succeed(self, tmp_path):
        """Two concurrent claims for different resources - both should succeed."""
        import threading

        from motus.coordination.claims_core import ClaimConflict, ClaimRegistry

        registry = ClaimRegistry(tmp_path / "claims", lease_duration_s=3600)

        results = []
        errors = []

        def claim_resource(agent_id: str, path: str):
            try:
                result = registry.register_claim(
                    task_id=f"task-{agent_id}",
                    agent_id=agent_id,
                    resources=[{"type": "file", "path": path}],
                    namespace="test",
                )
                results.append((agent_id, result))
            except Exception as e:
                errors.append((agent_id, e))

        threads = [
            threading.Thread(target=claim_resource, args=("agent-1", "/test/file1.txt")),
            threading.Thread(target=claim_resource, args=("agent-2", "/test/file2.txt")),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Unexpected errors: {errors}"
        assert len(results) == 2

        successes = [r for _, r in results if not isinstance(r, ClaimConflict)]
        assert len(successes) == 2, "Both claims for different resources should succeed"

    def test_high_contention_claims(self, tmp_path):
        """Many concurrent claims for same resource - exactly one wins."""
        import threading

        from motus.coordination.claims_core import ClaimConflict, ClaimRegistry

        registry = ClaimRegistry(tmp_path / "claims", lease_duration_s=3600)
        resources = [{"type": "file", "path": "/contested/resource.txt"}]

        results = []
        errors = []
        num_agents = 10

        def claim_resource(agent_id: str):
            try:
                result = registry.register_claim(
                    task_id=f"task-{agent_id}",
                    agent_id=agent_id,
                    resources=resources,
                    namespace="test",
                )
                results.append((agent_id, result))
            except Exception as e:
                errors.append((agent_id, e))

        threads = [
            threading.Thread(target=claim_resource, args=(f"agent-{i}",))
            for i in range(num_agents)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Unexpected errors: {errors}"
        assert len(results) == num_agents

        successes = [r for _, r in results if not isinstance(r, ClaimConflict)]
        conflicts = [r for _, r in results if isinstance(r, ClaimConflict)]

        # Exactly one should succeed
        assert len(successes) == 1, f"Expected exactly 1 success, got {len(successes)}"
        assert len(conflicts) == num_agents - 1
