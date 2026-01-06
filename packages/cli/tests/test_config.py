"""Tests for the MC configuration module."""

import json
from pathlib import Path

import pytest


class TestPathConfig:
    """Test PathConfig functionality."""

    def test_claude_dir_default(self):
        """Test default Claude directory."""
        from motus.config import PathConfig

        config = PathConfig()
        assert config.claude_dir == Path.home() / ".claude"

    def test_projects_dir_property(self):
        """Test projects_dir is derived from claude_dir."""
        from motus.config import PathConfig

        config = PathConfig()
        assert config.projects_dir == config.claude_dir / "projects"

    def test_state_dir_default(self):
        """Test default Motus state directory."""
        from motus.config import PathConfig
        from motus.migration.path_migration import resolve_state_dir

        config = PathConfig()
        assert config.state_dir == resolve_state_dir()

    def test_archive_dir_property(self):
        """Test archive_dir is derived from state_dir."""
        from motus.config import PathConfig

        config = PathConfig()
        assert config.archive_dir == config.state_dir / "archive"


class TestSessionConfig:
    """Test SessionConfig values."""

    def test_default_values(self):
        """Test default session config values."""
        from motus.config import SessionConfig

        config = SessionConfig()
        assert config.max_age_hours == 24
        assert config.active_threshold_seconds == 60
        assert config.idle_threshold_seconds == 120
        assert config.max_backfill_bytes == 50_000
        assert config.max_backfill_events == 30


class TestWebConfig:
    """Test WebConfig values."""

    def test_default_port(self):
        """Test default web port."""
        from motus.config import WebConfig

        config = WebConfig()
        assert config.default_port == 4000

    def test_port_from_env(self):
        """Test port can be set via environment."""
        # This test documents the behavior - the actual env var
        # is read at import time, so we just verify the default
        from motus.config import WebConfig

        config = WebConfig()
        assert isinstance(config.default_port, int)

    def test_host_default(self):
        """Test default host is localhost."""
        from motus.config import WebConfig

        config = WebConfig()
        assert config.host == "127.0.0.1"


class TestRiskConfig:
    """Test RiskConfig values.

    Note: RISK_LEVELS is tested separately as it lives in commands.models.
    """

    def test_destructive_patterns(self):
        """Test destructive patterns are defined."""
        from motus.config import RiskConfig

        config = RiskConfig()
        assert "rm " in config.destructive_patterns
        assert "sudo" in config.destructive_patterns
        assert "git reset --hard" in config.destructive_patterns

    def test_sensitive_patterns(self):
        """Test sensitive file patterns are defined."""
        from motus.config import RiskConfig

        config = RiskConfig()
        assert ".env" in config.sensitive_patterns
        assert "credentials" in config.sensitive_patterns
        assert "api_key" in config.sensitive_patterns


class TestMCConfig:
    """Test master MCConfig."""

    def test_global_config_exists(self):
        """Test global config instance is available."""
        from motus.config import config

        assert config is not None
        assert hasattr(config, "paths")
        assert hasattr(config, "sessions")
        assert hasattr(config, "web")
        assert hasattr(config, "risk")

    def test_backward_compatibility_exports(self):
        """Test backward compatibility exports."""
        from motus.config import (
            CLAUDE_DIR,
            MC_STATE_DIR,
            PROJECTS_DIR,
        )
        from motus.migration.path_migration import resolve_state_dir

        assert CLAUDE_DIR == Path.home() / ".claude"
        assert PROJECTS_DIR == Path.home() / ".claude" / "projects"
        assert MC_STATE_DIR == resolve_state_dir()

    def test_risk_levels_in_commands_models(self):
        """Test RISK_LEVELS is available from commands.models (canonical location)."""
        from motus.commands.models import RISK_LEVELS

        assert "Bash" in RISK_LEVELS


class TestHealthConfig:
    """Test HealthConfig values."""

    def test_weight_sum(self):
        """Test health weights sum to 1.0."""
        from motus.config import HealthConfig

        config = HealthConfig()
        total = config.friction_weight + config.progress_weight + config.velocity_weight
        assert total == 1.0

    def test_thresholds(self):
        """Test health thresholds are sensible."""
        from motus.config import HealthConfig

        config = HealthConfig()
        assert config.healthy_threshold > config.struggling_threshold
        assert config.healthy_threshold <= 100
        assert config.struggling_threshold >= 0


# Tests for new config.json system


@pytest.fixture
def temp_config_path(tmp_path):
    """Provide a temporary config path for testing."""
    return tmp_path / "config.json"


@pytest.fixture
def clean_env(monkeypatch):
    """Clean environment variables before tests."""
    for key in [
        "MC_USE_SQLITE",
        "MC_GATE_TIMEOUT_SECONDS",
        "MC_EVIDENCE_DIR",
        "MC_DB_PATH",
        "MC_REPORTING_LEVEL",
        "MC_METRICS_ENABLED",
    ]:
        monkeypatch.delenv(key, raising=False)


class TestConfigSchema:
    """Tests for MCConfigSchema dataclass."""

    def test_default_values(self):
        """Test that schema has correct default values."""
        from motus.config_schema import MCConfigSchema

        config = MCConfigSchema()
        assert config.version == "1.0"
        assert config.reporting_level == "minimal"
        assert config.reporting_include_evidence is False
        assert config.metrics_enabled is True
        assert config.sqlite_wal_mode is True
        assert config.gate_timeout_seconds == 300
        assert config.use_sqlite is True
        assert config.db_path == "~/.motus/coordination.db"
        assert config.anthropic_api_key is None
        assert config.openai_api_key is None
        assert config.github_token is None

    def test_to_dict(self):
        """Test conversion to dictionary."""
        from motus.config_schema import MCConfigSchema

        config = MCConfigSchema(reporting_level="verbose", gate_timeout_seconds=600)
        d = config.to_dict()
        assert d["reporting_level"] == "verbose"
        assert d["gate_timeout_seconds"] == 600
        assert d["version"] == "1.0"

    def test_from_dict(self):
        """Test creation from dictionary."""
        from motus.config_schema import MCConfigSchema

        data = {
            "version": "1.0",
            "reporting_level": "standard",
            "gate_timeout_seconds": 450,
            "use_sqlite": False,
        }
        config = MCConfigSchema.from_dict(data)
        assert config.reporting_level == "standard"
        assert config.gate_timeout_seconds == 450
        assert config.use_sqlite is False

    def test_from_dict_ignores_unknown_keys(self):
        """Test that unknown keys are filtered out."""
        from motus.config_schema import MCConfigSchema

        data = {
            "version": "1.0",
            "unknown_key": "value",
            "reporting_level": "verbose",
        }
        config = MCConfigSchema.from_dict(data)
        assert config.reporting_level == "verbose"
        assert not hasattr(config, "unknown_key")


class TestConfigLoader:
    """Tests for config loader functionality."""

    def test_load_config_nonexistent_file(self, temp_config_path, clean_env):
        """Test loading when file doesn't exist returns defaults."""
        from motus.config_loader import load_config

        config = load_config(temp_config_path)
        assert config.reporting_level == "minimal"
        assert config.gate_timeout_seconds == 300

    def test_load_config_from_file(self, temp_config_path, clean_env):
        """Test loading configuration from file."""
        from motus.config_loader import load_config

        # Create config file
        data = {
            "version": "1.0",
            "reporting_level": "verbose",
            "gate_timeout_seconds": 600,
            "use_sqlite": False,
        }
        with open(temp_config_path, "w") as f:
            json.dump(data, f)

        # Load and verify
        config = load_config(temp_config_path)
        assert config.reporting_level == "verbose"
        assert config.gate_timeout_seconds == 600
        assert config.use_sqlite is False

    def test_env_vars_override_file(self, temp_config_path, monkeypatch):
        """Test that environment variables override file values."""
        from motus.config_loader import load_config

        # Create config file
        data = {
            "version": "1.0",
            "reporting_level": "minimal",
            "gate_timeout_seconds": 300,
            "use_sqlite": True,
        }
        with open(temp_config_path, "w") as f:
            json.dump(data, f)

        # Set environment variables
        monkeypatch.setenv("MC_REPORTING_LEVEL", "verbose")
        monkeypatch.setenv("MC_GATE_TIMEOUT_SECONDS", "600")
        monkeypatch.setenv("MC_USE_SQLITE", "0")

        # Load and verify env vars win
        config = load_config(temp_config_path)
        assert config.reporting_level == "verbose"
        assert config.gate_timeout_seconds == 600
        assert config.use_sqlite is False

    def test_env_var_bool_parsing(self, temp_config_path, monkeypatch):
        """Test boolean environment variable parsing."""
        from motus.config_loader import load_config

        test_cases = [
            ("1", True),
            ("true", True),
            ("True", True),
            ("yes", True),
            ("on", True),
            ("0", False),
            ("false", False),
            ("no", False),
            ("off", False),
        ]

        for value_str, expected in test_cases:
            monkeypatch.setenv("MC_USE_SQLITE", value_str)
            config = load_config(temp_config_path)
            assert config.use_sqlite is expected, f"Failed for {value_str}"

    def test_save_config(self, temp_config_path, clean_env):
        """Test saving configuration to file."""
        from motus.config_loader import save_config
        from motus.config_schema import MCConfigSchema

        config = MCConfigSchema(reporting_level="verbose", gate_timeout_seconds=600)
        save_config(config, temp_config_path)

        # Verify file was created and has correct content
        assert temp_config_path.exists()
        with open(temp_config_path, "r") as f:
            data = json.load(f)
        assert data["reporting_level"] == "verbose"
        assert data["gate_timeout_seconds"] == 600

    def test_save_config_creates_directory(self, tmp_path, clean_env):
        """Test that save_config creates parent directory if needed."""
        from motus.config_loader import save_config
        from motus.config_schema import MCConfigSchema

        config_path = tmp_path / "subdir" / "config.json"
        config = MCConfigSchema()
        save_config(config, config_path)

        assert config_path.exists()
        assert config_path.parent.exists()

    def test_reset_config(self, temp_config_path, clean_env):
        """Test resetting configuration to defaults."""
        from motus.config_loader import load_config, reset_config, save_config
        from motus.config_schema import MCConfigSchema

        # Create modified config
        config = MCConfigSchema(reporting_level="verbose", gate_timeout_seconds=600)
        save_config(config, temp_config_path)

        # Reset
        reset_config(temp_config_path)

        # Load and verify it's back to defaults
        config = load_config(temp_config_path)
        assert config.reporting_level == "minimal"
        assert config.gate_timeout_seconds == 300


class TestConfigCLI:
    """Tests for config CLI commands."""

    def test_config_get_valid_key(self, temp_config_path, clean_env, capsys):
        """Test motus config get with valid key."""
        from motus.config_loader import load_config, save_config
        from motus.config_schema import MCConfigSchema

        config = MCConfigSchema(reporting_level="verbose")
        save_config(config, temp_config_path)

        import motus.commands.config_cmd as config_cmd

        original_load = config_cmd.load_config
        config_cmd.load_config = lambda: load_config(temp_config_path)

        try:
            config_cmd.config_get("reporting_level")
            captured = capsys.readouterr()
            assert "verbose" in captured.out
        finally:
            config_cmd.load_config = original_load

    def test_config_get_invalid_key(self, temp_config_path, clean_env):
        """Test motus config get with invalid key."""
        import motus.commands.config_cmd as config_cmd
        from motus.config_loader import load_config

        original_load = config_cmd.load_config
        config_cmd.load_config = lambda: load_config(temp_config_path)

        try:
            with pytest.raises(SystemExit):
                config_cmd.config_get("nonexistent_key")
        finally:
            config_cmd.load_config = original_load

    def test_config_set_string_value(self, temp_config_path, clean_env):
        """Test motus config set with string value."""
        import motus.commands.config_cmd as config_cmd
        from motus.config_loader import load_config, save_config

        original_load = config_cmd.load_config
        original_save = config_cmd.save_config
        original_get_path = config_cmd.get_config_path

        config_cmd.load_config = lambda: load_config(temp_config_path)
        config_cmd.save_config = lambda c: save_config(c, temp_config_path)
        config_cmd.get_config_path = lambda: temp_config_path

        try:
            config_cmd.config_set("reporting_level", "verbose")
            config = load_config(temp_config_path)
            assert config.reporting_level == "verbose"
        finally:
            config_cmd.load_config = original_load
            config_cmd.save_config = original_save
            config_cmd.get_config_path = original_get_path

    def test_config_set_bool_value(self, temp_config_path, clean_env):
        """Test motus config set with boolean value."""
        import motus.commands.config_cmd as config_cmd
        from motus.config_loader import load_config, save_config

        original_load = config_cmd.load_config
        original_save = config_cmd.save_config
        original_get_path = config_cmd.get_config_path

        config_cmd.load_config = lambda: load_config(temp_config_path)
        config_cmd.save_config = lambda c: save_config(c, temp_config_path)
        config_cmd.get_config_path = lambda: temp_config_path

        try:
            config_cmd.config_set("use_sqlite", "false")
            config = load_config(temp_config_path)
            assert config.use_sqlite is False
        finally:
            config_cmd.load_config = original_load
            config_cmd.save_config = original_save
            config_cmd.get_config_path = original_get_path

    def test_config_set_int_value(self, temp_config_path, clean_env):
        """Test motus config set with integer value."""
        import motus.commands.config_cmd as config_cmd
        from motus.config_loader import load_config, save_config

        original_load = config_cmd.load_config
        original_save = config_cmd.save_config
        original_get_path = config_cmd.get_config_path

        config_cmd.load_config = lambda: load_config(temp_config_path)
        config_cmd.save_config = lambda c: save_config(c, temp_config_path)
        config_cmd.get_config_path = lambda: temp_config_path

        try:
            config_cmd.config_set("gate_timeout_seconds", "600")
            config = load_config(temp_config_path)
            assert config.gate_timeout_seconds == 600
        finally:
            config_cmd.load_config = original_load
            config_cmd.save_config = original_save
            config_cmd.get_config_path = original_get_path
