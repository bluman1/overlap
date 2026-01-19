#!/usr/bin/env python3
"""
Overlap PostToolUse heartbeat hook.

Called after file edits to report activity to the Overlap server.
Collects the files being edited and sends them for classification.
"""

import json
import sys
import os

# Add scripts directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import logger
from config import is_configured, get_current_session
from api import api_request


def extract_file_path(tool_input: dict, tool_name: str) -> str | None:
    """Extract the file path from tool input based on tool type."""
    if tool_name in ("Write", "Edit"):
        return tool_input.get("file_path")
    elif tool_name == "MultiEdit":
        # MultiEdit has an array of edits
        edits = tool_input.get("edits", [])
        if edits:
            return edits[0].get("file_path")
    elif tool_name == "NotebookEdit":
        return tool_input.get("notebook_path")
    return None


def main():
    # Set up logging context
    session_id = get_current_session()
    logger.set_context(hook="PostToolUse", session_id=session_id)

    # Read hook input from stdin
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError as e:
        logger.warn("Failed to parse stdin JSON", error=str(e))
        sys.exit(0)

    # Check if configured
    if not is_configured():
        logger.debug("Not configured, skipping")
        sys.exit(0)

    # Get current session
    if not session_id:
        logger.debug("No active session, skipping")
        sys.exit(0)

    # Extract file path from tool input
    tool_name = input_data.get("tool_name", "")
    tool_input = input_data.get("tool_input", {})

    file_path = extract_file_path(tool_input, tool_name)
    if not file_path:
        logger.debug("No file path in tool input", tool_name=tool_name)
        sys.exit(0)

    # Make path relative to cwd for privacy
    cwd = input_data.get("cwd", os.getcwd())
    try:
        if os.path.isabs(file_path):
            file_path = os.path.relpath(file_path, cwd)
    except ValueError as e:
        # Can't make relative (different drive on Windows, etc.)
        logger.debug("Could not make path relative", path=file_path, error=str(e))

    logger.info("Sending heartbeat",
                tool_name=tool_name,
                file_path=file_path)

    try:
        # Send heartbeat with file info
        response = api_request("POST", f"/api/v1/sessions/{session_id}/heartbeat", {
            "files": [file_path],
        })

        result = response.get("data", {})
        logger.info("Heartbeat sent successfully",
                    file_path=file_path,
                    scope=result.get("semantic_scope"))

    except Exception as e:
        logger.error("Heartbeat failed", exc=e, file_path=file_path)
        import traceback
        print(f"[Overlap] Heartbeat failed: {e}", file=sys.stderr)
        print(f"[Overlap] Traceback: {traceback.format_exc()}", file=sys.stderr)

    sys.exit(0)


if __name__ == "__main__":
    main()
