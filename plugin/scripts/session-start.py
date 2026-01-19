#!/usr/bin/env python3
"""
Overlap SessionStart hook.

Called when a Claude Code session starts. Registers the session with the
Overlap server and stores the session ID for later use.
"""

import json
import sys
import os
from pathlib import Path

# Add scripts directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import logger
from config import is_configured, save_current_session, get_current_session
from api import api_request, get_hostname, get_device_name, get_git_info, is_remote_session


def main():
    # Set up logging context
    logger.set_context(hook="SessionStart")
    logger.info("Hook started",
                python=sys.executable,
                script=__file__,
                home=str(Path.home()),
                cwd=os.getcwd())

    # Also log to stderr for immediate visibility
    print(f"[Overlap] === SessionStart hook STARTED ===", file=sys.stderr)

    # Read hook input from stdin
    try:
        input_data = json.load(sys.stdin)
        logger.info("Received input", input_keys=list(input_data.keys()))
    except json.JSONDecodeError as e:
        logger.error("Failed to parse stdin JSON", exc=e)
        print(f"[Overlap] JSON decode error: {e}", file=sys.stderr)
        sys.exit(0)

    # Check if this is a startup or resume
    source = input_data.get("source", "")
    if source not in ("startup", "resume"):
        logger.info("Skipping - not startup/resume", source=source)
        print(f"[Overlap] Skipping - source is not startup/resume", file=sys.stderr)
        sys.exit(0)

    # Check if configured
    if not is_configured():
        logger.info("Not configured - exiting")
        print(f"[Overlap] NOT CONFIGURED - exiting. Run /overlap:config first", file=sys.stderr)
        sys.exit(0)
    logger.info("Configuration OK")

    # If resuming, check if we already have a session
    if source == "resume":
        existing_session = get_current_session()
        if existing_session:
            logger.info("Resuming existing session", session_id=existing_session)
            print(f"[Overlap] Found existing session {existing_session}, exiting", file=sys.stderr)
            sys.exit(0)
        logger.info("No existing session found, will create new one")

    # Get session info
    session_id = input_data.get("session_id", "")
    cwd = input_data.get("cwd", os.getcwd())
    logger.set_context(hook="SessionStart", session_id=session_id)

    # Get device and git info
    hostname = get_hostname()
    device_name = get_device_name()
    is_remote = is_remote_session()
    git_info = get_git_info(cwd)

    logger.info("Collected environment info",
                hostname=hostname,
                device_name=device_name,
                is_remote=is_remote,
                git_repo=git_info.get("repo_name"),
                git_branch=git_info.get("branch"))

    try:
        # Start session on server
        # Only include fields that have values (server rejects null for optional fields)
        request_data = {
            "session_id": session_id,
            "device_name": device_name,
            "hostname": hostname,
            "is_remote": is_remote,
            "worktree": cwd,
        }
        # Add optional git fields only if they have values
        if git_info.get("repo_name"):
            request_data["repo_name"] = git_info["repo_name"]
        if git_info.get("remote_url"):
            request_data["remote_url"] = git_info["remote_url"]
        if git_info.get("branch"):
            request_data["branch"] = git_info["branch"]

        logger.info("Starting session on server")
        print(f"[Overlap] Starting session...", file=sys.stderr)

        response = api_request("POST", "/api/v1/sessions/start", request_data)

        # Save session ID for later hooks
        server_session_id = response.get("data", {}).get("session_id")
        if server_session_id:
            save_current_session(server_session_id)
            logger.info("Session started successfully", server_session_id=server_session_id)
            print(f"[Overlap] Session started: {server_session_id}", file=sys.stderr)
        else:
            logger.warn("No session_id in server response", response_keys=list(response.keys()))
            print(f"[Overlap] WARNING: No session_id in response", file=sys.stderr)

        # Output context for Claude (shown in SessionStart)
        working_in = git_info.get("repo_name") or os.path.basename(cwd) or cwd
        output = {
            "hookSpecificOutput": {
                "hookEventName": "SessionStart",
                "additionalContext": f"[Overlap] Session tracking started. Working in: {working_in}"
            }
        }
        print(json.dumps(output))

    except Exception as e:
        logger.error("Failed to start session", exc=e)
        import traceback
        print(f"[Overlap] Failed to start session: {e}", file=sys.stderr)
        print(f"[Overlap] Traceback: {traceback.format_exc()}", file=sys.stderr)

    sys.exit(0)


if __name__ == "__main__":
    main()
