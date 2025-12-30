"""Tests for the checkpoint module."""

import json
import subprocess

import pytest


@pytest.fixture
def git_repo(tmp_path):
    """Create a temporary git repository for testing."""
    repo = tmp_path / "test_repo"
    repo.mkdir()

    # Initialize git repo
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=repo,
        check=True,
        capture_output=True,
    )

    # Create initial commit
    (repo / "README.md").write_text("# Test Repository")
    subprocess.run(["git", "add", "README.md"], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=repo,
        check=True,
        capture_output=True,
    )

    return repo


class TestCheckpointDataclass:
    """Test the Checkpoint dataclass."""

    def test_checkpoint_creation(self):
        """Test creating a Checkpoint object."""
        from motus.checkpoint import Checkpoint

        cp = Checkpoint(
            id="mc-20251202-120000",
            label="test checkpoint",
            timestamp="2025-12-02T12:00:00",
            git_stash_ref="stash@{0}",
            file_manifest=["file1.py", "file2.py"],
        )

        assert cp.id == "mc-20251202-120000"
        assert cp.label == "test checkpoint"
        assert len(cp.file_manifest) == 2
        assert cp.git_stash_ref == "stash@{0}"

    def test_checkpoint_optional_fields(self):
        """Test Checkpoint with optional fields omitted."""
        from motus.checkpoint import Checkpoint

        cp = Checkpoint(
            id="mc-test",
            label="minimal",
            timestamp="2025-12-02T12:00:00",
        )

        assert cp.git_stash_ref is None
        assert cp.file_manifest == []


class TestCreateCheckpoint:
    """Test checkpoint creation."""

    def test_create_checkpoint_success(self, git_repo):
        """Test successfully creating a checkpoint."""
        from motus.checkpoint import create_checkpoint

        # Modify a file
        test_file = git_repo / "test.txt"
        test_file.write_text("modified content")

        # Create checkpoint
        checkpoint = create_checkpoint("before refactor", git_repo)

        assert checkpoint.id.startswith("mc-")
        assert checkpoint.label == "before refactor"
        assert len(checkpoint.file_manifest) == 1
        assert "test.txt" in checkpoint.file_manifest[0]
        assert checkpoint.git_stash_ref is not None

        # Verify working directory is restored
        assert test_file.read_text() == "modified content"

    def test_create_checkpoint_no_changes(self, git_repo):
        """Test creating checkpoint with no changes raises error."""
        from motus.checkpoint import create_checkpoint

        # No modifications
        with pytest.raises(ValueError, match="No changes to checkpoint"):
            create_checkpoint("nothing to save", git_repo)

    def test_create_checkpoint_not_git_repo(self, tmp_path):
        """Test creating checkpoint outside git repo raises error."""
        from motus.checkpoint import create_checkpoint

        non_git_dir = tmp_path / "not_git"
        non_git_dir.mkdir()

        with pytest.raises(ValueError, match="Not in a git repository"):
            create_checkpoint("should fail", non_git_dir)

    def test_create_checkpoint_includes_untracked(self, git_repo):
        """Test checkpoint includes untracked files."""
        from motus.checkpoint import create_checkpoint

        # Create untracked file
        untracked = git_repo / "new_file.txt"
        untracked.write_text("untracked content")

        checkpoint = create_checkpoint("with untracked", git_repo)

        assert len(checkpoint.file_manifest) == 1
        assert "new_file.txt" in checkpoint.file_manifest[0]

    def test_create_multiple_checkpoints(self, git_repo):
        """Test creating multiple checkpoints."""
        from motus.checkpoint import create_checkpoint, list_checkpoints

        # Create first checkpoint
        (git_repo / "file1.txt").write_text("content 1")
        cp1 = create_checkpoint("checkpoint 1", git_repo)

        # Create second checkpoint
        (git_repo / "file2.txt").write_text("content 2")
        cp2 = create_checkpoint("checkpoint 2", git_repo)

        # List should show both (newest first)
        checkpoints = list_checkpoints(git_repo)
        assert len(checkpoints) == 2
        assert checkpoints[0].id == cp2.id
        assert checkpoints[1].id == cp1.id


class TestListCheckpoints:
    """Test listing checkpoints."""

    def test_list_checkpoints_empty(self, git_repo):
        """Test listing checkpoints when none exist."""
        from motus.checkpoint import list_checkpoints

        checkpoints = list_checkpoints(git_repo)
        assert checkpoints == []

    def test_list_checkpoints_not_git_repo(self, tmp_path):
        """Test listing checkpoints outside git repo."""
        from motus.checkpoint import list_checkpoints

        non_git_dir = tmp_path / "not_git"
        non_git_dir.mkdir()

        checkpoints = list_checkpoints(non_git_dir)
        assert checkpoints == []

    def test_list_checkpoints_after_creation(self, git_repo):
        """Test listing checkpoints after creating some."""
        from motus.checkpoint import create_checkpoint, list_checkpoints

        # Create checkpoint
        (git_repo / "test.txt").write_text("content")
        cp = create_checkpoint("test", git_repo)

        # List checkpoints
        checkpoints = list_checkpoints(git_repo)
        assert len(checkpoints) == 1
        assert checkpoints[0].id == cp.id
        assert checkpoints[0].label == "test"

    def test_list_checkpoints_ordering(self, git_repo):
        """Test checkpoints are ordered newest first."""
        from motus.checkpoint import create_checkpoint, list_checkpoints

        # Create checkpoints with different IDs (timestamps)
        (git_repo / "file1.txt").write_text("content 1")
        cp1 = create_checkpoint("first", git_repo)

        (git_repo / "file2.txt").write_text("content 2")
        cp2 = create_checkpoint("second", git_repo)

        checkpoints = list_checkpoints(git_repo)
        # Most recent first
        assert checkpoints[0].id == cp2.id
        assert checkpoints[1].id == cp1.id

    def test_list_checkpoints_corrupted_file(self, git_repo):
        """Test listing checkpoints with corrupted metadata file."""
        from motus.checkpoint import list_checkpoints

        # Create corrupted metadata file
        mc_dir = git_repo / ".mc"
        mc_dir.mkdir(exist_ok=True)
        (mc_dir / "checkpoints.json").write_text("invalid json{")

        # Should return empty list instead of crashing
        checkpoints = list_checkpoints(git_repo)
        assert checkpoints == []


class TestRollbackCheckpoint:
    """Test checkpoint rollback."""

    def test_rollback_checkpoint_success(self, git_repo):
        """Test successfully rolling back to a checkpoint."""
        from motus.checkpoint import create_checkpoint, rollback_checkpoint

        # Create and modify file
        test_file = git_repo / "test.txt"
        test_file.write_text("original content")

        # Create checkpoint
        checkpoint = create_checkpoint("before changes", git_repo)

        # Modify file again
        test_file.write_text("modified content")

        # Rollback
        restored = rollback_checkpoint(checkpoint.id, git_repo)

        assert restored.id == checkpoint.id
        # File should be back to original
        assert test_file.read_text() == "original content"

    def test_rollback_partial_id(self, git_repo):
        """Test rollback with partial checkpoint ID."""
        from motus.checkpoint import create_checkpoint, rollback_checkpoint

        # Create checkpoint
        test_file = git_repo / "test.txt"
        test_file.write_text("content")
        checkpoint = create_checkpoint("test", git_repo)

        # Modify again
        test_file.write_text("modified")

        # Rollback using partial ID (first 10 chars)
        partial_id = checkpoint.id[:10]
        restored = rollback_checkpoint(partial_id, git_repo)

        assert restored.id == checkpoint.id

    def test_rollback_checkpoint_not_found(self, git_repo):
        """Test rollback with non-existent checkpoint ID."""
        from motus.checkpoint import rollback_checkpoint

        with pytest.raises(ValueError, match="Checkpoint not found"):
            rollback_checkpoint("nonexistent-id", git_repo)

    def test_rollback_not_git_repo(self, tmp_path):
        """Test rollback outside git repo raises error."""
        from motus.checkpoint import rollback_checkpoint

        non_git_dir = tmp_path / "not_git"
        non_git_dir.mkdir()

        with pytest.raises(ValueError, match="Not in a git repository"):
            rollback_checkpoint("any-id", non_git_dir)

    def test_rollback_saves_current_state(self, git_repo):
        """Test rollback saves current state before applying."""
        from motus.checkpoint import create_checkpoint, rollback_checkpoint

        # Create checkpoint
        test_file = git_repo / "test.txt"
        test_file.write_text("checkpoint content")
        checkpoint = create_checkpoint("test", git_repo)

        # Make new changes
        test_file.write_text("new content")

        # Rollback
        rollback_checkpoint(checkpoint.id, git_repo)

        # Current state should be in git stash
        result = subprocess.run(
            ["git", "stash", "list"],
            cwd=git_repo,
            capture_output=True,
            text=True,
        )
        assert "mc-rollback-safety" in result.stdout


class TestDiffCheckpoint:
    """Test checkpoint diff."""

    def test_diff_checkpoint_success(self, git_repo):
        """Test showing diff of a checkpoint."""
        from motus.checkpoint import create_checkpoint, diff_checkpoint

        # Create file and checkpoint
        test_file = git_repo / "test.txt"
        test_file.write_text("original content")
        checkpoint = create_checkpoint("test", git_repo)

        # Get diff
        diff_output = diff_checkpoint(checkpoint.id, git_repo)

        assert "test.txt" in diff_output
        assert "original content" in diff_output

    def test_diff_checkpoint_not_found(self, git_repo):
        """Test diff with non-existent checkpoint."""
        from motus.checkpoint import diff_checkpoint

        with pytest.raises(ValueError, match="Checkpoint not found"):
            diff_checkpoint("nonexistent-id", git_repo)

    def test_diff_partial_id(self, git_repo):
        """Test diff with partial checkpoint ID."""
        from motus.checkpoint import create_checkpoint, diff_checkpoint

        # Create checkpoint
        test_file = git_repo / "test.txt"
        test_file.write_text("content")
        checkpoint = create_checkpoint("test", git_repo)

        # Get diff using partial ID
        partial_id = checkpoint.id[:10]
        diff_output = diff_checkpoint(partial_id, git_repo)

        assert "test.txt" in diff_output

    def test_diff_not_git_repo(self, tmp_path):
        """Test diff outside git repo raises error."""
        from motus.checkpoint import diff_checkpoint

        non_git_dir = tmp_path / "not_git"
        non_git_dir.mkdir()

        with pytest.raises(ValueError, match="Not in a git repository"):
            diff_checkpoint("any-id", non_git_dir)


class TestCheckpointPersistence:
    """Test checkpoint metadata persistence."""

    def test_checkpoint_metadata_saved(self, git_repo):
        """Test checkpoint metadata is saved to .mc/checkpoints.json."""
        from motus.checkpoint import create_checkpoint

        # Create checkpoint
        test_file = git_repo / "test.txt"
        test_file.write_text("content")
        checkpoint = create_checkpoint("test checkpoint", git_repo)

        # Check metadata file exists
        metadata_file = git_repo / ".mc" / "checkpoints.json"
        assert metadata_file.exists()

        # Check content
        data = json.loads(metadata_file.read_text())
        assert len(data) == 1
        assert data[0]["id"] == checkpoint.id
        assert data[0]["label"] == "test checkpoint"
        assert len(data[0]["file_manifest"]) == 1

    def test_checkpoint_metadata_format(self, git_repo):
        """Test checkpoint metadata has correct JSON format."""
        from motus.checkpoint import create_checkpoint

        # Create checkpoint
        (git_repo / "test.txt").write_text("content")
        create_checkpoint("test", git_repo)  # Result not needed for this test

        # Load and validate JSON structure
        metadata_file = git_repo / ".mc" / "checkpoints.json"
        data = json.loads(metadata_file.read_text())

        assert isinstance(data, list)
        assert len(data) == 1

        cp_data = data[0]
        assert "id" in cp_data
        assert "label" in cp_data
        assert "timestamp" in cp_data
        assert "git_stash_ref" in cp_data
        assert "file_manifest" in cp_data


class TestGitIntegration:
    """Test git integration aspects."""

    def test_git_stash_created(self, git_repo):
        """Test that git stash is actually created."""
        from motus.checkpoint import create_checkpoint

        # Create checkpoint
        (git_repo / "test.txt").write_text("content")
        create_checkpoint("test", git_repo)

        # Check git stash list
        result = subprocess.run(
            ["git", "stash", "list"],
            cwd=git_repo,
            capture_output=True,
            text=True,
        )

        assert "mc-checkpoint: test" in result.stdout

    def test_working_directory_restored(self, git_repo):
        """Test working directory is restored after checkpoint."""
        from motus.checkpoint import create_checkpoint

        # Create and modify files
        file1 = git_repo / "file1.txt"
        file2 = git_repo / "file2.txt"
        file1.write_text("content 1")
        file2.write_text("content 2")

        # Create checkpoint
        create_checkpoint("test", git_repo)

        # Files should still exist and have same content
        assert file1.read_text() == "content 1"
        assert file2.read_text() == "content 2"

    def test_checkpoint_with_staged_changes(self, git_repo):
        """Test checkpoint works with staged changes."""
        from motus.checkpoint import create_checkpoint

        # Create and stage a file
        test_file = git_repo / "staged.txt"
        test_file.write_text("staged content")
        subprocess.run(["git", "add", "staged.txt"], cwd=git_repo, check=True)

        # Create checkpoint
        checkpoint = create_checkpoint("with staged", git_repo)

        assert len(checkpoint.file_manifest) == 1
        assert "staged.txt" in checkpoint.file_manifest[0]


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_checkpoint_with_special_characters_in_label(self, git_repo):
        """Test checkpoint with special characters in label."""
        from motus.checkpoint import create_checkpoint

        # Create checkpoint with special chars
        (git_repo / "test.txt").write_text("content")
        checkpoint = create_checkpoint("test: 'before' \"changes\"", git_repo)

        assert checkpoint.label == "test: 'before' \"changes\""

    def test_checkpoint_with_very_long_label(self, git_repo):
        """Test checkpoint with very long label."""
        from motus.checkpoint import create_checkpoint

        # Create checkpoint with long label
        long_label = "a" * 500
        (git_repo / "test.txt").write_text("content")
        checkpoint = create_checkpoint(long_label, git_repo)

        assert checkpoint.label == long_label

    def test_checkpoint_with_empty_label(self, git_repo):
        """Test checkpoint with empty label."""
        from motus.checkpoint import create_checkpoint

        (git_repo / "test.txt").write_text("content")
        checkpoint = create_checkpoint("", git_repo)

        assert checkpoint.label == ""
        assert checkpoint.id.startswith("mc-")

    def test_checkpoint_in_subdirectory(self, git_repo):
        """Test creating checkpoint from a subdirectory."""
        from motus.checkpoint import create_checkpoint

        # Create subdirectory
        subdir = git_repo / "subdir"
        subdir.mkdir()

        # Modify file in subdirectory
        (subdir / "test.txt").write_text("content")

        # Create checkpoint from subdirectory
        checkpoint = create_checkpoint("from subdir", subdir)

        # Should still work and reference git root
        assert checkpoint.id.startswith("mc-")
        assert len(checkpoint.file_manifest) == 1
