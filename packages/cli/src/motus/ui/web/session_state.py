"""
Backward compatibility alias for SessionState.

The SessionStateManager class has been renamed to SessionState.
This module provides an alias for backward compatibility with tests.
"""

from motus.ui.web.state import SessionState

# Alias for backward compatibility
SessionStateManager = SessionState

__all__ = ["SessionStateManager", "SessionState"]
