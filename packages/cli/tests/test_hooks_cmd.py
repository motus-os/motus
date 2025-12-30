"""Tests for hooks command."""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from motus.commands.hooks_cmd import (
    get_mc_hook_config,
    install_hooks_command,
    uninstall_hooks_command,
)


class TestGetMcHookConfig:
    """Test get_mc_hook_config function."""

    def test_get_mc_hook_config_structure(self):
        """Test hook config has correct structure."""
        config = get_mc_hook_config()

        assert "hooks" in config
        assert "SessionStart" in config["hooks"]
        assert "UserPromptSubmit" in config["hooks"]

    def test_get_mc_hook_config_session_start(self):
        """Test SessionStart hook configuration."""
        config = get_mc_hook_config()

        session_start = config["hooks"]["SessionStart"]
        assert len(session_start) == 1
        assert session_start[0]["matcher"] == "*"
        assert len(session_start[0]["hooks"]) == 1

        hook = session_start[0]["hooks"][0]
        assert hook["type"] == "command"
        assert "motus.hooks" in hook["command"]
        assert "session_start_hook" in hook["command"]
        assert hook["timeout"] == 5000

    def test_get_mc_hook_config_user_prompt_submit(self):
        """Test UserPromptSubmit hook configuration."""
        config = get_mc_hook_config()

        user_prompt = config["hooks"]["UserPromptSubmit"]
        assert len(user_prompt) == 1
        assert user_prompt[0]["matcher"] == "*"
        assert len(user_prompt[0]["hooks"]) == 1

        hook = user_prompt[0]["hooks"][0]
        assert hook["type"] == "command"
        assert "motus.hooks" in hook["command"]
        assert "user_prompt_hook" in hook["command"]
        assert hook["timeout"] == 3000


class TestInstallHooksCommand:
    """Test install_hooks_command function."""

    def test_install_hooks_new_settings_file(self, capsys):
        """Test installing hooks creates new settings file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_file = Path(tmpdir) / "settings.json"

            with patch("motus.commands.hooks_cmd.CLAUDE_SETTINGS", settings_file):
                install_hooks_command()

            # Verify file was created
            assert settings_file.exists()

            # Verify content
            with open(settings_file, "r") as f:
                settings = json.load(f)

            assert "hooks" in settings
            assert "SessionStart" in settings["hooks"]
            assert "UserPromptSubmit" in settings["hooks"]

            captured = capsys.readouterr()
            assert "installed" in captured.out.lower()

    def test_install_hooks_creates_parent_directory(self):
        """Test install_hooks_command creates parent directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_file = Path(tmpdir) / "subdir" / "settings.json"
            assert not settings_file.parent.exists()

            with patch("motus.commands.hooks_cmd.CLAUDE_SETTINGS", settings_file):
                install_hooks_command()

            # Parent directory should be created
            assert settings_file.parent.exists()
            assert settings_file.exists()

    def test_install_hooks_existing_settings_no_hooks(self, capsys):
        """Test installing hooks into existing settings without hooks."""
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_file = Path(tmpdir) / "settings.json"

            # Create existing settings file without hooks
            existing_settings = {"some_setting": "value", "another": 123}
            with open(settings_file, "w") as f:
                json.dump(existing_settings, f)

            with patch("motus.commands.hooks_cmd.CLAUDE_SETTINGS", settings_file):
                install_hooks_command()

            # Verify hooks were added, other settings preserved
            with open(settings_file, "r") as f:
                settings = json.load(f)

            assert "hooks" in settings
            assert settings["some_setting"] == "value"
            assert settings["another"] == 123

            captured = capsys.readouterr()
            assert "Added SessionStart hook" in captured.out
            assert "Added UserPromptSubmit hook" in captured.out

    def test_install_hooks_existing_hooks(self, capsys):
        """Test installing hooks when hooks already exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_file = Path(tmpdir) / "settings.json"

            # Create settings with existing hooks
            existing_settings = {
                "hooks": {
                    "SessionStart": [
                        {
                            "matcher": "*",
                            "hooks": [
                                {
                                    "type": "command",
                                    "command": "echo test",
                                }
                            ],
                        }
                    ]
                }
            }
            with open(settings_file, "w") as f:
                json.dump(existing_settings, f)

            with patch("motus.commands.hooks_cmd.CLAUDE_SETTINGS", settings_file):
                install_hooks_command()

            # Verify MC hooks were added
            with open(settings_file, "r") as f:
                settings = json.load(f)

            # Should have both existing and MC hooks
            assert len(settings["hooks"]["SessionStart"]) == 2

            captured = capsys.readouterr()
            assert "Added SessionStart hook" in captured.out

    def test_install_hooks_mc_hooks_already_installed(self, capsys):
        """Test installing when MC hooks are already present."""
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_file = Path(tmpdir) / "settings.json"

            # Create settings with MC hooks already installed
            mc_config = get_mc_hook_config()
            with open(settings_file, "w") as f:
                json.dump(mc_config, f)

            with patch("motus.commands.hooks_cmd.CLAUDE_SETTINGS", settings_file):
                install_hooks_command()

            captured = capsys.readouterr()
            assert "already exists" in captured.out

    def test_install_hooks_invalid_json(self, capsys):
        """Test installing hooks when existing file has invalid JSON."""
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_file = Path(tmpdir) / "settings.json"

            # Create invalid JSON file
            with open(settings_file, "w") as f:
                f.write("{ invalid json }")

            with patch("motus.commands.hooks_cmd.CLAUDE_SETTINGS", settings_file):
                install_hooks_command()

            # Should handle gracefully and create new settings
            with open(settings_file, "r") as f:
                settings = json.load(f)

            assert "hooks" in settings

            captured = capsys.readouterr()
            assert "Warning" in captured.out or "invalid" in captured.out

    def test_install_hooks_preserves_existing_hook_types(self, capsys):
        """Test that other hook types are preserved."""
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_file = Path(tmpdir) / "settings.json"

            existing_settings = {
                "hooks": {
                    "SessionStart": [
                        {
                            "matcher": "*",
                            "hooks": [{"type": "command", "command": "echo existing"}],
                        }
                    ],
                    "OtherHookType": [
                        {
                            "matcher": "*",
                            "hooks": [{"type": "command", "command": "echo other"}],
                        }
                    ],
                }
            }
            with open(settings_file, "w") as f:
                json.dump(existing_settings, f)

            with patch("motus.commands.hooks_cmd.CLAUDE_SETTINGS", settings_file):
                install_hooks_command()

            with open(settings_file, "r") as f:
                settings = json.load(f)

            # OtherHookType should be preserved
            assert "OtherHookType" in settings["hooks"]
            assert settings["hooks"]["OtherHookType"] == existing_settings["hooks"]["OtherHookType"]


class TestUninstallHooksCommand:
    """Test uninstall_hooks_command function."""

    def test_uninstall_hooks_no_settings_file(self, capsys):
        """Test uninstalling when settings file doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_file = Path(tmpdir) / "nonexistent.json"

            with patch("motus.commands.hooks_cmd.CLAUDE_SETTINGS", settings_file):
                uninstall_hooks_command()

            captured = capsys.readouterr()
            assert "No Claude settings found" in captured.out

    def test_uninstall_hooks_invalid_json(self, capsys):
        """Test uninstalling when settings file has invalid JSON."""
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_file = Path(tmpdir) / "settings.json"

            with open(settings_file, "w") as f:
                f.write("{ invalid json }")

            with patch("motus.commands.hooks_cmd.CLAUDE_SETTINGS", settings_file):
                uninstall_hooks_command()

            captured = capsys.readouterr()
            assert "Error" in captured.out or "Invalid" in captured.out

    def test_uninstall_hooks_no_hooks_section(self, capsys):
        """Test uninstalling when settings has no hooks section."""
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_file = Path(tmpdir) / "settings.json"

            with open(settings_file, "w") as f:
                json.dump({"other_setting": "value"}, f)

            with patch("motus.commands.hooks_cmd.CLAUDE_SETTINGS", settings_file):
                uninstall_hooks_command()

            captured = capsys.readouterr()
            assert "No hooks configured" in captured.out

    def test_uninstall_hooks_removes_mc_hooks(self, capsys):
        """Test uninstalling removes MC hooks."""
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_file = Path(tmpdir) / "settings.json"

            # Install MC hooks first
            mc_config = get_mc_hook_config()
            with open(settings_file, "w") as f:
                json.dump(mc_config, f)

            with patch("motus.commands.hooks_cmd.CLAUDE_SETTINGS", settings_file):
                uninstall_hooks_command()

            # Verify MC hooks were removed
            with open(settings_file, "r") as f:
                settings = json.load(f)

            # hooks section should be empty or not exist
            assert "hooks" not in settings or len(settings.get("hooks", {})) == 0

            captured = capsys.readouterr()
            assert "Removed" in captured.out

    def test_uninstall_hooks_preserves_other_hooks(self, capsys):
        """Test uninstalling preserves non-MC hooks."""
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_file = Path(tmpdir) / "settings.json"

            settings = {
                "hooks": {
                    "SessionStart": [
                        {
                            "matcher": "*",
                            "hooks": [
                                {
                                    "type": "command",
                                    "command": 'python3 -c "from motus.hooks import session_start_hook; session_start_hook()"',
                                }
                            ],
                        },
                        {
                            "matcher": "*",
                            "hooks": [{"type": "command", "command": "echo other hook"}],
                        },
                    ],
                    "OtherHookType": [
                        {
                            "matcher": "*",
                            "hooks": [{"type": "command", "command": "echo keep this"}],
                        }
                    ],
                }
            }

            with open(settings_file, "w") as f:
                json.dump(settings, f)

            with patch("motus.commands.hooks_cmd.CLAUDE_SETTINGS", settings_file):
                uninstall_hooks_command()

            with open(settings_file, "r") as f:
                result = json.load(f)

            # MC hooks should be removed, others preserved
            assert "hooks" in result
            assert "OtherHookType" in result["hooks"]
            assert len(result["hooks"]["SessionStart"]) == 1
            assert "echo other hook" in str(result["hooks"]["SessionStart"])

            captured = capsys.readouterr()
            assert "Removed" in captured.out

    def test_uninstall_hooks_cleans_up_empty_arrays(self, capsys):
        """Test uninstalling cleans up empty hook type arrays."""
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_file = Path(tmpdir) / "settings.json"

            # Only MC hooks, no other hooks
            mc_config = get_mc_hook_config()
            with open(settings_file, "w") as f:
                json.dump(mc_config, f)

            with patch("motus.commands.hooks_cmd.CLAUDE_SETTINGS", settings_file):
                uninstall_hooks_command()

            with open(settings_file, "r") as f:
                result = json.load(f)

            # Empty hooks object should be removed
            assert "hooks" not in result or result.get("hooks") == {}

    def test_uninstall_hooks_counts_removed(self, capsys):
        """Test uninstalling reports correct count of removed hooks."""
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_file = Path(tmpdir) / "settings.json"

            mc_config = get_mc_hook_config()
            with open(settings_file, "w") as f:
                json.dump(mc_config, f)

            with patch("motus.commands.hooks_cmd.CLAUDE_SETTINGS", settings_file):
                uninstall_hooks_command()

            captured = capsys.readouterr()
            # Should report removing hooks (2 hook types)
            assert "Removed" in captured.out
            assert "2" in captured.out or "MC hooks" in captured.out

    def test_uninstall_hooks_handles_mixed_hook_formats(self, capsys):
        """Test uninstalling handles various hook formats."""
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_file = Path(tmpdir) / "settings.json"

            settings = {
                "hooks": {
                    "SessionStart": [
                        # MC hook
                        {
                            "matcher": "*",
                            "hooks": [
                                {
                                    "type": "command",
                                    "command": 'python3 -c "from motus.hooks import session_start_hook; session_start_hook()"',
                                }
                            ],
                        },
                        # Non-MC hook
                        {
                            "matcher": "*.py",
                            "hooks": [{"type": "command", "command": "echo python file"}],
                        },
                    ]
                }
            }

            with open(settings_file, "w") as f:
                json.dump(settings, f)

            with patch("motus.commands.hooks_cmd.CLAUDE_SETTINGS", settings_file):
                uninstall_hooks_command()

            with open(settings_file, "r") as f:
                result = json.load(f)

            # MC hook removed, Python hook preserved
            assert len(result["hooks"]["SessionStart"]) == 1
            assert "python file" in str(result["hooks"]["SessionStart"])
