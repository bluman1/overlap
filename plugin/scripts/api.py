"""
Overlap API client.

Simple HTTP client for communicating with the Overlap server.
"""

import json
import socket
import subprocess
import sys
from typing import Optional
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

from config import get_config
import logger


def api_request(
    method: str,
    endpoint: str,
    data: Optional[dict] = None,
    timeout: int = 5
) -> dict:
    """
    Make an API request to the Overlap server.

    Args:
        method: HTTP method (GET, POST, etc.)
        endpoint: API endpoint (e.g., /api/v1/sessions/start)
        data: JSON data to send (for POST/PUT)
        timeout: Request timeout in seconds

    Returns:
        Response data as dict

    Raises:
        Exception: If request fails
    """
    config = get_config()

    if not config.get("server_url"):
        logger.warn("API request skipped - no server_url configured", endpoint=endpoint)
        raise Exception("Overlap server URL not configured")

    url = f"{config['server_url'].rstrip('/')}{endpoint}"

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {config.get('user_token', '')}",
        "X-Team-Token": config.get("team_token", ""),
    }

    body = json.dumps(data).encode() if data else None

    request = Request(url, data=body, headers=headers, method=method)

    # Start request logging
    req_ctx = logger.log_request(method, url, len(body) if body else 0)
    req_ctx.log_start()

    try:
        with urlopen(request, timeout=timeout) as response:
            response_data = json.loads(response.read().decode())
            req_ctx.log_success(response.status)
            return response_data
    except HTTPError as e:
        error_body = e.read().decode()
        try:
            error_data = json.loads(error_body)
            error_msg = error_data.get("error", f"HTTP {e.code}")
            req_ctx.log_error(e.code, error_msg=error_msg)
            raise Exception(error_msg)
        except json.JSONDecodeError:
            req_ctx.log_error(e.code, error_msg=error_body[:200])
            raise Exception(f"HTTP {e.code}: {error_body}")
    except URLError as e:
        req_ctx.log_error(0, exc=e)
        raise Exception(f"Connection error: {e.reason}")
    except socket.timeout as e:
        req_ctx.log_error(0, exc=e)
        raise Exception("Request timed out")


def get_hostname() -> str:
    """Get the current machine's hostname."""
    return socket.gethostname()


def get_device_name() -> str:
    """Get a friendly device name."""
    hostname = get_hostname()
    # Try to get a more descriptive name on macOS
    try:
        result = subprocess.run(
            ["scutil", "--get", "ComputerName"],
            capture_output=True,
            text=True,
            timeout=2
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return hostname


def get_git_info(cwd: str) -> dict:
    """Get git repository information."""
    info = {
        "repo_name": None,
        "remote_url": None,
        "branch": None,
    }

    try:
        # Get remote URL
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            cwd=cwd,
            timeout=2
        )
        if result.returncode == 0:
            info["remote_url"] = result.stdout.strip()
            # Extract repo name from URL
            remote = info["remote_url"]
            if remote.endswith(".git"):
                remote = remote[:-4]
            info["repo_name"] = remote.split("/")[-1]
        else:
            logger.debug("Git remote not found", cwd=cwd, stderr=result.stderr.strip())

        # Get current branch
        result = subprocess.run(
            ["git", "branch", "--show-current"],
            capture_output=True,
            text=True,
            cwd=cwd,
            timeout=2
        )
        if result.returncode == 0:
            info["branch"] = result.stdout.strip()
        else:
            logger.debug("Git branch not found", cwd=cwd, stderr=result.stderr.strip())

    except subprocess.TimeoutExpired:
        logger.warn("Git command timed out", cwd=cwd)
    except FileNotFoundError:
        logger.debug("Git not installed or not in PATH")

    return info


def is_remote_session() -> bool:
    """Check if running in a remote session (SSH, etc.)."""
    # Check common remote indicators
    if os.environ.get("SSH_CLIENT") or os.environ.get("SSH_TTY"):
        return True
    if os.environ.get("CLAUDE_CODE_REMOTE") == "true":
        return True
    return False


def register_pending_session(transcript_path: str) -> str | None:
    """
    Register a pending session with the server.

    This is called lazily on first tool use (PreToolUse or PostToolUse)
    to filter out ghost sessions that never do actual work.

    Args:
        transcript_path: The Claude session transcript path

    Returns:
        The Overlap session ID if successful, None otherwise
    """
    from config import (
        get_pending_session,
        clear_pending_session,
        save_session_for_transcript,
        get_session_for_transcript,
    )

    # Check if already registered
    existing = get_session_for_transcript(transcript_path)
    if existing:
        logger.info("Session already registered", overlap_session_id=existing)
        return existing

    # Get pending session info
    pending = get_pending_session(transcript_path)
    if not pending:
        logger.debug("No pending session found", transcript_path=transcript_path)
        return None

    logger.info("Registering pending session", transcript_path=transcript_path)
    print(f"[Overlap] Registering session...", file=sys.stderr)

    try:
        # Build request data from pending info
        request_data = {
            "session_id": pending.get("session_id", ""),
            "device_name": pending.get("device_name", ""),
            "hostname": pending.get("hostname", ""),
            "is_remote": pending.get("is_remote", False),
            "worktree": pending.get("worktree", ""),
        }
        # Add optional git fields only if they have values
        if pending.get("repo_name"):
            request_data["repo_name"] = pending["repo_name"]
        if pending.get("remote_url"):
            request_data["remote_url"] = pending["remote_url"]
        if pending.get("branch"):
            request_data["branch"] = pending["branch"]

        response = api_request("POST", "/api/v1/sessions/start", request_data)

        overlap_session_id = response.get("data", {}).get("session_id")
        if overlap_session_id:
            # Save the registered session and clear pending
            save_session_for_transcript(transcript_path, overlap_session_id, pending.get("worktree", ""))
            clear_pending_session(transcript_path)
            logger.info("Session registered successfully",
                        overlap_session_id=overlap_session_id,
                        transcript_path=transcript_path)
            print(f"[Overlap] Session started: {overlap_session_id}", file=sys.stderr)
            return overlap_session_id
        else:
            logger.warn("No session_id in server response")
            return None

    except Exception as e:
        logger.error("Failed to register pending session", exc=e)
        print(f"[Overlap] Failed to register session: {e}", file=sys.stderr)
        return None


def ensure_session_registered(transcript_path: str, session_id: str, cwd: str) -> str | None:
    """
    Ensure a session is registered, using lazy registration.

    Checks in order:
    1. Already registered session
    2. Pending session (register it)
    3. Fresh registration (if transcript file exists)

    Args:
        transcript_path: The Claude session transcript path
        session_id: Claude's session ID from hook input
        cwd: Current working directory from hook input

    Returns:
        The Overlap session ID if successful, None otherwise
    """
    from config import (
        get_session_for_transcript,
        get_pending_session,
        save_pending_session,
    )

    # 1. Check if already registered
    existing = get_session_for_transcript(transcript_path)
    if existing:
        return existing

    # 2. Check for pending session
    if get_pending_session(transcript_path):
        return register_pending_session(transcript_path)

    # 3. Check if transcript file exists now (lazy check)
    if not os.path.exists(transcript_path):
        logger.debug("Transcript file still does not exist", transcript_path=transcript_path)
        return None

    # Transcript exists but no pending - gather fresh info and register
    logger.info("Transcript exists, gathering session info for registration",
                transcript_path=transcript_path)

    hostname = get_hostname()
    device_name = get_device_name()
    is_remote = is_remote_session()
    git_info = get_git_info(cwd)

    session_info = {
        "session_id": session_id,
        "device_name": device_name,
        "hostname": hostname,
        "is_remote": is_remote,
        "worktree": cwd,
    }
    if git_info.get("repo_name"):
        session_info["repo_name"] = git_info["repo_name"]
    if git_info.get("remote_url"):
        session_info["remote_url"] = git_info["remote_url"]
    if git_info.get("branch"):
        session_info["branch"] = git_info["branch"]

    # Save pending and register
    save_pending_session(transcript_path, session_info)
    return register_pending_session(transcript_path)


# Import os for is_remote_session
import os
