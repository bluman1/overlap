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


# Import os for is_remote_session
import os
