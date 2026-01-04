# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""
Gemini Bridge for Motus.

Use this script to bridge a running Gemini session (like a CLI or Agent)
into the Motus observability plane.

Usage:
    # Initialize
    bridge = GeminiBridge("my-session-id")

    # Log events
    bridge.log_user("List files in src")
    bridge.log_thinking("I should use ls -R")
    bridge.log_tool("ls", {"args": ["-R", "src"]})
"""

import uuid
from typing import Any, Optional

from motus import Tracer


class GeminiBridge:
    def __init__(self, session_id: Optional[str] = None):
        self.session_id = session_id or f"gemini-{uuid.uuid4().hex[:8]}"
        self.tracer = Tracer(name="gemini-cli", session_id=self.session_id)

    def log_user(self, content: str):
        """Log a user message as a thinking event with user context."""
        # Map user messages to thinking events with a prefix for clarity
        self.tracer.thinking(f"[User request] {content}")

    def log_thinking(self, content: str):
        self.tracer.thinking(content)

    def log_tool(self, name: str, input_data: dict, output_data: Any = None):
        self.tracer.tool(name, input_data, output=output_data)

    def log_decision(self, decision: str, reasoning: str):
        self.tracer.decision(decision, reasoning)

if __name__ == "__main__":
    # Simple CLI for the bridge
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--session", help="Session ID")
    parser.add_argument("--type", choices=["thinking", "tool", "decision"], required=True)
    parser.add_argument("--content", help="Content or Tool Name")
    parser.add_argument("--data", help="JSON data for tool input/output")

    args = parser.parse_args()

    bridge = GeminiBridge(args.session)

    if args.type == "thinking":
        bridge.log_thinking(args.content)
    elif args.type == "tool":
        import json
        data = json.loads(args.data or "{}")
        bridge.log_tool(args.content, data)
    elif args.type == "decision":
        bridge.log_decision(args.content, "")

    print(f"Logged to session: {bridge.session_id}")
