"""Path security utilities."""

from pathlib import Path


class PathTraversalError(ValueError):
    """Raised when path traversal is detected."""
    pass


def validate_safe_path(
    user_path: str,
    allowed_base: Path | None = None,
    allow_absolute: bool = False,
) -> Path:
    """Validate user-provided path is safe to read.

    Args:
        user_path: The path string from user input
        allowed_base: If provided, resolved path must be under this directory
        allow_absolute: If False, reject absolute paths

    Returns:
        Resolved, validated Path object

    Raises:
        PathTraversalError: If path contains traversal attempts or escapes allowed_base
    """
    if not user_path or not user_path.strip():
        raise PathTraversalError("Path cannot be empty")

    path = Path(user_path).expanduser()

    # Check for traversal attempts in path segments
    if ".." in path.parts:
        raise PathTraversalError("Path traversal (..) not allowed")

    # Check absolute paths
    if not allow_absolute and path.is_absolute():
        # Allow home directory expansion (~ becomes absolute)
        if not user_path.startswith("~"):
            raise PathTraversalError("Absolute paths not allowed")

    # Resolve and check boundary
    try:
        resolved = path.resolve()
    except (OSError, RuntimeError) as e:
        raise PathTraversalError(f"Invalid path: {e}")

    if allowed_base:
        base_resolved = allowed_base.resolve()
        try:
            resolved.relative_to(base_resolved)
        except ValueError:
            raise PathTraversalError(
                f"Path escapes allowed directory: {allowed_base}"
            )

    return resolved


def validate_session_path(session_path: str) -> Path:
    """Validate a session file path.

    Sessions must be under ~/.motus/ or ~/.claude/
    """
    if not session_path or not session_path.strip():
        raise PathTraversalError("Path cannot be empty")

    path = Path(session_path).expanduser()

    # Check for traversal in path segments
    if ".." in path.parts:
        raise PathTraversalError("Path traversal not allowed")

    resolved = path.resolve()

    # Sessions must be under allowed directories
    home = Path.home()
    allowed_dirs = [
        home / ".motus",
        home / ".claude",
    ]

    for allowed in allowed_dirs:
        try:
            resolved.relative_to(allowed.resolve())
            return resolved
        except ValueError:
            continue

    raise PathTraversalError("Session path must be under ~/.motus/ or ~/.claude/")
