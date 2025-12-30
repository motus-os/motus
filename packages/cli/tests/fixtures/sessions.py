"""Session fixtures for testing."""

import json
import tempfile
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Generator, Optional


def create_mock_session(
    session_id: str = "test-session-123",
    project_path: str = "/home/user/projects/myapp",
    events: Optional[list] = None,
    age_hours: float = 0,
) -> tuple[Path, dict]:
    """Create a mock session file with events.

    Args:
        session_id: Session identifier
        project_path: Project path to encode
        events: List of event dicts to write
        age_hours: How old the session should appear

    Returns:
        Tuple of (file_path, session_info_dict)
    """
    import os
    from datetime import timedelta

    events = events or []

    # Create temp file
    fd, path = tempfile.mkstemp(suffix=".jsonl", prefix=f"{session_id}_")

    with os.fdopen(fd, "w") as f:
        for event in events:
            f.write(json.dumps(event) + "\n")

    path = Path(path)

    # Adjust modification time if needed
    if age_hours > 0:
        old_time = (datetime.now() - timedelta(hours=age_hours)).timestamp()
        os.utime(path, (old_time, old_time))

    session_info = {
        "session_id": session_id,
        "file_path": path,
        "project_path": project_path,
        "size": path.stat().st_size,
        "last_modified": datetime.fromtimestamp(path.stat().st_mtime),
    }

    return path, session_info


def create_session_directory(
    base_dir: Path,
    project_path: str = "/home/user/projects/myapp",
    session_id: str = "abc123",
    events: Optional[list] = None,
) -> Path:
    """Create a mock Claude session directory structure.

    Args:
        base_dir: Base directory (e.g., tmpdir)
        project_path: Project path to encode
        session_id: Session ID prefix
        events: Events to write to transcript

    Returns:
        Path to the created transcript file
    """
    events = events or []

    # Encode project path: /home/user/projects/myapp -> home-user-projects-myapp
    encoded_path = project_path.replace("/", "-").lstrip("-")
    dir_name = f"{session_id}-{encoded_path}"

    # Create directory structure
    projects_dir = base_dir / "projects"
    session_dir = projects_dir / dir_name
    session_dir.mkdir(parents=True, exist_ok=True)

    # Create transcript
    transcript = session_dir / "transcript.jsonl"
    with open(transcript, "w") as f:
        for event in events:
            f.write(json.dumps(event) + "\n")

    return transcript


@contextmanager
def mock_claude_projects_dir(sessions: Optional[list[dict]] = None) -> Generator[Path, None, None]:
    """Context manager that creates a mock Claude projects directory.

    Args:
        sessions: List of session configs, each with:
            - project_path: str
            - session_id: str (optional)
            - events: list (optional)
            - age_hours: float (optional)

    Yields:
        Path to the mock projects directory
    """
    import os
    from datetime import timedelta

    sessions = sessions or []

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        projects_dir = tmpdir / "projects"
        projects_dir.mkdir()

        for session_config in sessions:
            project_path = session_config.get("project_path", "/test/project")
            session_id = session_config.get("session_id", "test123")
            events = session_config.get("events", [])
            age_hours = session_config.get("age_hours", 0)

            # Create session directory
            encoded = project_path.replace("/", "-").lstrip("-")
            session_dir = projects_dir / f"{session_id}-{encoded}"
            session_dir.mkdir()

            # Create transcript
            transcript = session_dir / "transcript.jsonl"
            with open(transcript, "w") as f:
                for event in events:
                    f.write(json.dumps(event) + "\n")

            # Adjust age
            if age_hours > 0:
                old_time = (datetime.now() - timedelta(hours=age_hours)).timestamp()
                os.utime(transcript, (old_time, old_time))

        yield tmpdir
